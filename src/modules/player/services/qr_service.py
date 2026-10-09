from datetime import datetime, timezone
from uuid import uuid4

import jwt
from fastapi import status

from modules.audit.services import record as audit
from modules.player.models import PlayerModel, PlayerQrModel
from modules.player.models.player_qr_schemas import PlayerQrResponse
from modules.season.models import SeasonModel, SeasonTeamModel
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from project_helpers.functions.jwt_handler import JWT_ALGORITHM, JWT_SECRET_KEY

QR_AUDIENCE = "scc-player-attendance"


def issue_player_qr(db, player, season_id, user, regenerate=False):
    # Serialize simultaneous issues for the same player, including first issue.
    player = (
        db.query(PlayerModel)
        .filter(PlayerModel.id == player.id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    if not player.avatar:
        raise ErrorException(Error.PLAYER_PHOTO_REQUIRED)
    season = db.query(SeasonModel).filter(SeasonModel.id == season_id).first()
    if season is None:
        raise ErrorException(
            Error.NOT_FOUND,
            message="Season not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    enrolled = db.query(SeasonTeamModel.id).filter(
        SeasonTeamModel.seasonId == season_id,
        SeasonTeamModel.teamId == player.teamId,
    ).first()
    if player.teamId is None or enrolled is None:
        raise ErrorException(
            Error.PLAYER_NOT_IN_TEAM,
            message="The player's team is not enrolled in this season",
        )

    credential = db.query(PlayerQrModel).filter(
        PlayerQrModel.playerId == player.id,
        PlayerQrModel.seasonId == season_id,
    ).with_for_update().first()
    if credential is not None and not regenerate and (
        credential.revokedAt is not None or credential.teamId != player.teamId
    ):
        raise ErrorException(
            Error.INVALID_PLAYER_QR,
            message="Regenerate this player's QR code after a revocation or team change",
            status_code=status.HTTP_409_CONFLICT,
        )
    if credential is None or regenerate:
        if credential is None:
            credential = PlayerQrModel(playerId=player.id, seasonId=season_id)
            db.add(credential)
        credential.teamId = player.teamId
        credential.version = uuid4().hex
        credential.issuedAt = datetime.utcnow()
        credential.revokedAt = None
        db.flush()
        audit(
            db, user, "PLAYER_QR_ISSUED", "Player", player.id,
            summary="Player QR credential issued",
            details={"seasonId": season_id, "regenerated": regenerate},
        )

    token = jwt.encode(
        {
            "aud": QR_AUDIENCE,
            "credentialId": credential.id,
            "version": credential.version,
            "iat": int(credential.issuedAt.replace(tzinfo=timezone.utc).timestamp()),
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )
    return PlayerQrResponse(
        playerId=player.id, playerName=player.name,
        teamId=player.teamId, teamName=player.teamName,
        seasonId=season.id, seasonName=season.name,
        issuedAt=credential.issuedAt, token=token,
    )


def revoke_player_qr(db, player, season_id, user):
    # Same lock order as issuance.
    db.query(PlayerModel).filter(PlayerModel.id == player.id).with_for_update().one()
    credential = db.query(PlayerQrModel).filter(
        PlayerQrModel.playerId == player.id,
        PlayerQrModel.seasonId == season_id,
    ).with_for_update().first()
    if credential is None:
        raise ErrorException(
            Error.NOT_FOUND,
            message="Player QR credential not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if credential.revokedAt is None:
        credential.revokedAt = datetime.utcnow()
        audit(
            db, user, "PLAYER_QR_REVOKED", "Player", player.id,
            summary="Player QR credential revoked",
            details={"seasonId": season_id},
        )


def resolve_player_qr(db, token, match, lock=False):
    try:
        claims = jwt.decode(
            token, JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            audience=QR_AUDIENCE,
            options={"require": ["aud", "credentialId", "version", "iat"]},
        )
        if type(claims["credentialId"]) is not int or not isinstance(
            claims["version"], str
        ):
            raise ValueError("Invalid credential claims")
    except (jwt.PyJWTError, ValueError, TypeError):
        raise ErrorException(Error.INVALID_PLAYER_QR)
    query = db.query(PlayerQrModel).filter(PlayerQrModel.id == claims["credentialId"])
    credential = query.populate_existing().first()
    player = None
    if credential is not None and lock:
        # Match -> player -> credential: transfers and QR issuance lock the
        # player first too, so neither stale membership nor a deadlock can
        # slip through a simultaneous transfer and check-in.
        player = db.query(PlayerModel).filter(
            PlayerModel.id == credential.playerId
        ).with_for_update().populate_existing().first()
        credential = query.with_for_update().populate_existing().first()
    if (
        credential is None
        or credential.revokedAt is not None
        or credential.version != claims["version"]
    ):
        raise ErrorException(Error.INVALID_PLAYER_QR)
    if credential.seasonId != match.seasonId:
        raise ErrorException(Error.QR_WRONG_SEASON)
    if not lock:
        player = db.query(PlayerModel).filter(
            PlayerModel.id == credential.playerId
        ).populate_existing().first()
    enrolled = db.query(SeasonTeamModel.id).filter(
        SeasonTeamModel.seasonId == match.seasonId,
        SeasonTeamModel.teamId == credential.teamId,
    ).first()
    if (
        player is None
        or player.teamId != credential.teamId
        or player.teamId not in (match.homeTeamId, match.awayTeamId)
        or enrolled is None
    ):
        raise ErrorException(Error.PLAYER_NOT_IN_TEAM)
    if not player.avatar:
        raise ErrorException(Error.PLAYER_PHOTO_REQUIRED)
    return player
