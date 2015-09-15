"""Something."""
from waflib import TaskGen
import time
import threading
import os

l = threading.Lock()


def collect_data_from_run(f, task):
    """Something."""
    def wrap_run():
        start = time.time()
        ret = f()
        stop = time.time()
        l.acquire()
        for output in task.outputs:
            filesize = os.path.getsize(task.outputs[0].nice_path()) / 1024.0
            print('{output} ({time:0.3f}s, {filesize:0.3f}kb)'.format(
                output=task.outputs[0].name,
                time=(stop - start),
                filesize=filesize))
        l.release()
        return ret
    return wrap_run


@TaskGen.feature('*')
@TaskGen.after('process_source')
def time_compiled_tasks(self):
    """Something."""
    if hasattr(self, 'compiled_tasks'):
        for t in self.compiled_tasks:
            t.run = collect_data_from_run(t.run, t)
