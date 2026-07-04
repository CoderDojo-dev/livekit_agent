import asyncio
from config.settings import Settings
from providers.session_factory import build_agent_session

async def test():
    settings = Settings()
    try:
        session = build_agent_session(settings, 'fr')
        print("Session built successfully with turn detector:", type(session.turn_detector))
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())
