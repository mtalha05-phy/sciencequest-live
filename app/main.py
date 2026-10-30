"""
FastAPI application and real-time WebSocket hub for ScienceQuest Live.
Coordinates game state, Twitch chat, Quark AI companion, scoring, and OBS overlay.
"""

from contextlib import asynccontextmanager
from typing import Dict, Any, List, Set
import asyncio
import json
import logging
import os
import pathlib

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx

from app.config import settings
from app.game.state import GameStateManager, MISSION_DEFINITIONS
from app.game.scoring import ScoreManager, BADGE_METADATA
from app.twitch.client import TwitchService
from app.ai.quark import QuarkCompanion

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sciencequest.server")

STATIC_DIR = pathlib.Path(__file__).resolve().parent / "static"

# Singletons
game_state = GameStateManager()
score_manager = ScoreManager()
quark = QuarkCompanion(api_key=settings.openai_api_key, model=settings.openai_model)
twitch_service: TwitchService = None


class ConnectionManager:
    """Manages active WebSockets connections to broadcast real-time game updates."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active_connections:
            return
        payload = json.dumps(message)
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.active_connections.discard(d)


ws_manager = ConnectionManager()


# --- Event Bridge Callbacks ---

def handle_twitch_chat(username: str, text: str, is_simulated: bool):
    """Broadcasts chat messages from live Twitch or simulation mode."""
    asyncio.create_task(
        ws_manager.broadcast({
            "event": "chat_message",
            "username": username,
            "text": text,
            "is_simulated": is_simulated,
        })
    )


def handle_twitch_command(action: Dict[str, Any]):
    """Processes parsed Twitch chat commands in the game state."""
    action_type = action.get("type")
    username = action.get("username", "Viewer")

    if action_type == "vote":
        opt = action.get("option", "")
        if game_state.record_vote(username, opt):
            # Broadcast updated voting status
            asyncio.create_task(
                ws_manager.broadcast({
                    "event": "vote_update",
                    "voting_status": game_state.get_voting_status(),
                })
            )

    elif action_type == "set_param":
        param = action.get("param")
        val = action.get("value")
        if game_state.update_parameter(param, val):
            asyncio.create_task(broadcast_full_state())

    elif action_type == "set_mission":
        m_id = action.get("mission_id")
        if game_state.set_active_mission(m_id):
            asyncio.create_task(broadcast_full_state())

    elif action_type == "ask_quark":
        q = action.get("question", "")
        asyncio.create_task(process_quark_question(q, username))

    elif action_type == "run_experiment":
        # Resolve voting and run calculation
        if game_state.voting_open:
            asyncio.create_task(resolve_current_round())
        else:
            game_state.recalculate_current_physics()
            asyncio.create_task(broadcast_full_state())

    elif action_type == "start_round":
        game_state.start_voting_round(duration_seconds=45)
        asyncio.create_task(broadcast_full_state())


async def broadcast_full_state():
    await ws_manager.broadcast({
        "event": "state_update",
        "state": game_state.get_full_client_state(),
    })


async def process_quark_question(question: str, username: str):
    m_def = game_state.get_mission_def()
    answer = await quark.answer_user_question(
        question=question,
        mission_id=game_state.active_mission_id,
        mission_title=m_def["title"],
        current_params=game_state.mission_params[game_state.active_mission_id],
        physics_result=game_state.active_physics_result,
    )
    await ws_manager.broadcast({
        "event": "quark_speech",
        "question": question,
        "username": username,
        "answer": answer,
        "level": quark.current_explanation_level,
    })


async def resolve_current_round():
    res = game_state.close_and_resolve_voting()
    m_def = game_state.get_mission_def()
    # Award points and badge
    score_manager.record_prediction_round(
        mission_id=game_state.active_mission_id,
        correct_voters=res["correct_voters"],
        incorrect_voters=res["incorrect_voters"],
        badge_awarded_id=m_def.get("badge_id"),
    )
    # Quark explains resolution
    explanation = await quark.explain_active_experiment(
        mission_id=game_state.active_mission_id,
        mission_title=m_def["title"],
        current_params=game_state.mission_params[game_state.active_mission_id],
        physics_result=game_state.active_physics_result,
    )
    await ws_manager.broadcast({
        "event": "round_resolved",
        "round_result": res,
        "quark_explanation": explanation,
        "leaderboard": score_manager.get_leaderboard(5),
    })
    await broadcast_full_state()


# --- Lifespan Management ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    global twitch_service
    logger.info("Initializing ScienceQuest Live Services...")
    twitch_service = TwitchService(
        channel=settings.twitch_channel,
        bot_nick=settings.twitch_bot_nickname,
        oauth_token=settings.twitch_oauth_token,
        simulation_mode=settings.simulation_mode,
        on_command_callback=handle_twitch_command,
        on_chat_callback=handle_twitch_chat,
    )
    await twitch_service.start()
    yield
    logger.info("Shutting down ScienceQuest Live Services...")
    if twitch_service:
        await twitch_service.stop()


app = FastAPI(title="ScienceQuest Live", version="1.0.0", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --- HTML Routes ---

@app.get("/")
async def get_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(index_file)


@app.get("/overlay")
async def get_overlay():
    overlay_file = STATIC_DIR / "overlay.html"
    if not overlay_file.exists():
        raise HTTPException(status_code=404, detail="overlay.html not found")
    return FileResponse(overlay_file)
 
 
# --- Twitch OAuth Authentication Routes ---
 
@app.get("/auth/twitch/login")
async def twitch_login():
    """Redirects streamer or bot to Twitch OAuth authorization page."""
    if not settings.twitch_client_id:
        return JSONResponse(
            status_code=400,
            content={
                "error": "TWITCH_CLIENT_ID is not configured in .env.",
                "message": "Please register your application in the Twitch Developer Console and configure TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET in .env.",
                "configured_redirect_uri": settings.twitch_redirect_uri,
            }
        )
    from urllib.parse import quote
    redirect_uri = settings.twitch_redirect_uri
    scopes = "chat:read+chat:edit+whispers:read"
    auth_url = (
        f"https://id.twitch.tv/oauth2/authorize"
        f"?client_id={settings.twitch_client_id}"
        f"&redirect_uri={quote(redirect_uri, safe='')}"
        f"&response_type=code"
        f"&scope={scopes}"
        f"&force_verify=true"
    )
    return RedirectResponse(auth_url)
 
 
@app.get("/auth/twitch/callback")
async def twitch_callback(code: str = Query(None), error: str = Query(None), error_description: str = Query(None)):
    """Handles OAuth redirect callback from Twitch Developer Console."""
    if error:
        logger.error(f"Twitch OAuth Error: {error} - {error_description}")
        return RedirectResponse(f"/?twitch_error={error}")
 
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code missing from callback.")
 
    if not settings.twitch_client_secret:
        return JSONResponse(
            status_code=400,
            content={
                "error": "TWITCH_CLIENT_SECRET is not configured in .env.",
                "message": "Confidential client requires TWITCH_CLIENT_SECRET in .env to perform server-to-server token exchange.",
            }
        )
 
    # Server-side token exchange (Confidential Client Type)
    token_url = "https://id.twitch.tv/oauth2/token"
    payload = {
        "client_id": settings.twitch_client_id,
        "client_secret": settings.twitch_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.twitch_redirect_uri,
    }
 
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(token_url, data=payload)
            if resp.status_code == 200:
                data = resp.json()
                access_token = data.get("access_token")
                # Update running twitch service
                settings.twitch_oauth_token = access_token
                settings.simulation_mode = False
                if twitch_service:
                    twitch_service.oauth_token = access_token
                    twitch_service.simulation_mode = False
                    await twitch_service.stop()
                    await twitch_service.start()
                logger.info("Successfully authenticated with Twitch via OAuth code exchange!")
                return RedirectResponse("/?twitch=authenticated")
            else:
                logger.error(f"Failed to exchange Twitch code: {resp.text}")
                return RedirectResponse("/?twitch_error=token_exchange_failed")
    except Exception as e:
        logger.error(f"Exception during Twitch token exchange: {e}")
        return RedirectResponse("/?twitch_error=exchange_exception")
 
 
# --- REST API Endpoints ---

@app.get("/api/state")
async def get_state():
    return game_state.get_full_client_state()


@app.post("/api/mission/{mission_id}")
async def change_mission(mission_id: str):
    if not game_state.set_active_mission(mission_id):
        raise HTTPException(status_code=400, detail="Invalid mission ID")
    await broadcast_full_state()
    # Quark welcomes players to the new mission
    m_def = game_state.get_mission_def()
    intro = await quark.explain_active_experiment(
        mission_id=m_def["id"],
        mission_title=m_def["title"],
        current_params=game_state.mission_params[m_def["id"]],
        physics_result=game_state.active_physics_result,
    )
    await ws_manager.broadcast({
        "event": "quark_speech",
        "username": "Quark",
        "question": f"Starting {m_def['title']}!",
        "answer": intro,
        "level": quark.current_explanation_level,
    })
    return game_state.get_full_client_state()


class ParameterUpdate(BaseModel):
    param: str
    value: Any


@app.post("/api/parameter")
async def update_param(data: ParameterUpdate):
    if not game_state.update_parameter(data.param, data.value):
        raise HTTPException(status_code=400, detail="Invalid parameter name or out of allowed range")
    await broadcast_full_state()
    return {
        "status": "success",
        "current_params": game_state.mission_params[game_state.active_mission_id],
        "physics_result": game_state.active_physics_result,
    }


class VotingStartRequest(BaseModel):
    duration_seconds: int = 45


@app.post("/api/voting/start")
async def start_voting(data: VotingStartRequest):
    status = game_state.start_voting_round(duration_seconds=data.duration_seconds)
    await ws_manager.broadcast({"event": "voting_started", "voting_status": status})
    return status


class VoteRequest(BaseModel):
    username: str
    option: str


@app.post("/api/voting/vote")
async def cast_vote(data: VoteRequest):
    if not game_state.record_vote(data.username, data.option):
        raise HTTPException(status_code=400, detail="Voting closed or invalid option")
    status = game_state.get_voting_status()
    await ws_manager.broadcast({"event": "vote_update", "voting_status": status})
    return status


@app.post("/api/voting/resolve")
async def resolve_voting():
    await resolve_current_round()
    return game_state.last_round_result


class AskQuarkRequest(BaseModel):
    question: str
    username: str = "Player"
    level: str = "SCIENTIST"


@app.post("/api/quark/ask")
async def ask_quark_endpoint(data: AskQuarkRequest):
    quark.set_explanation_level(data.level)
    m_def = game_state.get_mission_def()
    ans = await quark.answer_user_question(
        question=data.question,
        mission_id=game_state.active_mission_id,
        mission_title=m_def["title"],
        current_params=game_state.mission_params[game_state.active_mission_id],
        physics_result=game_state.active_physics_result,
        level=data.level,
    )
    await ws_manager.broadcast({
        "event": "quark_speech",
        "question": data.question,
        "username": data.username,
        "answer": ans,
        "level": data.level,
    })
    return {"question": data.question, "answer": ans, "level": data.level}


class QuarkLevelRequest(BaseModel):
    level: str


@app.post("/api/quark/level")
async def set_quark_level(data: QuarkLevelRequest):
    if not quark.set_explanation_level(data.level):
        raise HTTPException(status_code=400, detail="Invalid level. Choose EXPLORER, SCIENTIST, or RESEARCHER.")
    return {"current_level": quark.current_explanation_level}


@app.get("/api/leaderboard")
async def get_leaderboard():
    return {
        "leaderboard": score_manager.get_leaderboard(10),
        "badges": BADGE_METADATA,
    }


@app.get("/api/status")
async def get_service_status():
    return {
        "simulation_mode": settings.simulation_mode,
        "twitch_connected": twitch_service.is_running if twitch_service else False,
        "twitch_live": twitch_service.is_live_configured() if twitch_service else False,
        "twitch_channel": settings.twitch_channel or "(None - Running in Simulation Mode)",
        "twitch_oauth_configured": bool(settings.twitch_client_id and settings.twitch_client_secret),
        "twitch_redirect_uri": settings.twitch_redirect_uri,
        "twitch_client_id_set": bool(settings.twitch_client_id),
        "ai_enabled": bool(settings.openai_api_key),
        "ai_model": settings.openai_model,
        "active_mission": game_state.active_mission_id,
        "explanation_level": quark.current_explanation_level,
    }


class SendChatRequest(BaseModel):
    username: str
    text: str


@app.post("/api/chat/send")
async def send_chat(data: SendChatRequest):
    # Parse as Twitch command or general chat
    handle_twitch_chat(data.username, data.text, is_simulated=True)
    action = twitch_service.parser.parse_message(data.username, data.text, is_mod_or_streamer=True)
    if action:
        handle_twitch_command(action)
    return {"status": "sent"}


# --- WebSocket Route ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send initial full state immediately upon connection
        await websocket.send_text(
            json.dumps({
                "event": "init_state",
                "state": game_state.get_full_client_state(),
                "leaderboard": score_manager.get_leaderboard(5),
            })
        )
        while True:
            # Keep reading incoming client websocket messages
            data_text = await websocket.receive_text()
            try:
                data = json.loads(data_text)
                msg_type = data.get("type")
                if msg_type == "ping":
                    await websocket.send_text(json.dumps({"event": "pong"}))
                elif msg_type == "vote":
                    u = data.get("username", "WebPlayer")
                    opt = data.get("option", "")
                    if game_state.record_vote(u, opt):
                        await ws_manager.broadcast({
                            "event": "vote_update",
                            "voting_status": game_state.get_voting_status(),
                        })
                elif msg_type == "param":
                    p = data.get("param")
                    v = data.get("value")
                    if game_state.update_parameter(p, v):
                        await broadcast_full_state()
            except Exception as ex:
                logger.warning(f"Error handling WS message: {ex}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
