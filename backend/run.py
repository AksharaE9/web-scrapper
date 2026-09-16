import asyncio
import sys

if sys.platform == "win32" and sys.version_info < (3, 14):
    try:
        _set_policy = getattr(asyncio, "set_event_loop_policy", None)
        _selector_policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
        if _set_policy and _selector_policy:
            _set_policy(_selector_policy())
    except Exception:
        pass
    try:
        import uvicorn.loops.asyncio
        uvicorn.loops.asyncio.asyncio_loop_factory = lambda use_subprocess=False: asyncio.SelectorEventLoop
    except Exception:
        pass

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True, loop="asyncio")
