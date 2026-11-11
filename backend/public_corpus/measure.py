"""Offline candidate measurement; no HTTP listener or publication approval."""
import os
import statistics
import sys
import time


def memory():
    if sys.platform=='win32':
        import ctypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ['peak','rss','a','b','c','d','commit','peak_commit']]
        p=Counters();p.cb=ctypes.sizeof(p)
        cur=ctypes.windll.kernel32.GetCurrentProcess;cur.restype=ctypes.c_void_p
        fn=ctypes.windll.psapi.GetProcessMemoryInfo
        fn.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong]
        if not fn(cur(),ctypes.byref(p),p.cb):raise ctypes.WinError()
        return dict(resident_mib=round(p.rss/1024**2,3),peak_resident_mib=round(p.peak/1024**2,3),method='Windows GetProcessMemoryInfo')
    if sys.platform.startswith('linux'):
        import resource
        from pathlib import Path
        current=int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        return dict(resident_mib=round(current/1024**2,3),peak_resident_mib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,3),method='Linux procfs and getrusage')
    return dict(resident_mib=None,peak_resident_mib=None,method='unsupported; not estimated')


def measure(directory,pin,query,iterations=9):
    start=time.perf_counter()
    # Include the actual HTTP dependency footprint, but never start a listener.
    from backend.chat.api import create_app
    from .runtime import PublicIndex
    index=PublicIndex(directory,pin,preview=True)
    startup=time.perf_counter()-start
    if not index.passages:raise ValueError('Candidate unavailable; no measurement fabricated')
    latencies=[]
    for _ in range(iterations):
        start=time.perf_counter();hits=index.search(query);latencies.append((time.perf_counter()-start)*1000)
    return dict(mode=index.mode,preview_only=True,publication_approved=False,passages=len(index.passages),
        startup_seconds=round(startup,4),memory=memory(),query=query,query_hits=len(hits),iterations=iterations,
        latency_median_ms=round(statistics.median(latencies),3),latency_max_ms=round(max(latencies),3),
        forbidden_imports=[n for n in ['torch','faiss','sentence_transformers','pymupdf','backend.review.service','backend.publication.bindings'] if n in sys.modules],
        scope='Fresh-process offline candidate with HTTP dependencies; not Render/Linux capacity certification')
