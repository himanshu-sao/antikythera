import asyncio
# Ensure a default event loop exists for any imported module that calls
# ``asyncio.get_event_loop()`` before an explicit loop is created.
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
