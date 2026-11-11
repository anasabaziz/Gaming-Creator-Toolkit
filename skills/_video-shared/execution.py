"""Bounded subprocess execution and optional job journaling."""
import errno
import os
from pathlib import Path
import subprocess
import time
import uuid
import tempfile
from job_state import identity, record, snapshot, update


def emit(kind, data):
    root = os.environ.get('VIDEO_JOB_RECORD')
    if root:
        state = snapshot(root)
        stage_id = os.environ.get('VIDEO_JOB_STAGE')
        if not stage_id or stage_id not in state['stages'] or not state['stages'][stage_id].get('contract'):
            raise ValueError('Journal execution requires VIDEO_JOB_STAGE with a registered contract')
        stage = state['stages'].get(stage_id, {})
        if kind in ('tool_started', 'stage_started') and stage.get('status') != 'running':
            raise ValueError('Execution requires a running stage; diagnose and register resume_change before retry')
        cid = stage.get('contract')
        if cid not in state.get('contracts', {}):
            raise ValueError('Journal execution requires a registered contract')
        contract = state.get('contracts', {}).get(cid, {})
        record(root, kind, {**data, 'job_stage': stage_id, 'contract': cid, 'baseline': contract.get('baseline')})


def progress_run(args, timeout, callback):
    """FFmpeg progress is data, not completion proof. Always reap interrupted children."""
    with tempfile.TemporaryDirectory(prefix='ffmpeg-progress-') as folder:
        progress = Path(folder) / 'progress.txt'
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            process = subprocess.Popen([args[0], '-progress', str(progress), '-nostats', *args[1:]], stdout=stdout, stderr=stderr)
            start = time.monotonic()
            last = None
            try:
                while True:
                    elapsed = time.monotonic() - start
                    if elapsed > timeout:
                        raise subprocess.TimeoutExpired(args, timeout)
                    if progress.exists():
                        lines = progress.read_text(encoding='utf-8', errors='replace').splitlines()
                        fields = dict(line.split('=', 1) for line in lines if '=' in line)
                        raw = fields.get('out_time_us')
                        if raw and raw != 'N/A' and raw != last:
                            callback({'processed_media_seconds': max(0, int(raw) / 1000000), 'elapsed_seconds': elapsed})
                            last = raw
                    if process.poll() is not None:
                        break
                    time.sleep(.2)
            except BaseException:
                process.kill(); process.wait()
                raise
            stdout.seek(0); stderr.seek(0)
            return subprocess.CompletedProcess(args, process.returncode, stdout.read(), stderr.read())


def block_failure(details):
    root = os.environ.get('VIDEO_JOB_RECORD')
    if root:
        update(root, 'stage', {'id': os.environ['VIDEO_JOB_STAGE'], 'status': 'blocked',
               'failure': details,
               'next_action': 'Diagnose failure; record changed cause/input/capability before retry'})


def execute(args, *, timeout=None, safe_retry=False, retries=1, progress=None):
    args = [str(a) for a in args]
    if timeout is None:
        timeout = float(os.environ.get('VIDEO_COMMAND_TIMEOUT', '3600'))
    if not 0 < timeout <= 86400 or not 0 <= retries <= 2:
        raise ValueError('Timeout must be 0..86400 seconds; retries 0..2')
    root = os.environ.get('VIDEO_JOB_RECORD')
    if root:
        snapshot(root)  # Refuse execution if the requested journal is unavailable.
    operation = uuid.uuid4().hex
    executable = Path(args[0])
    details = {'operation': operation, 'executable': identity(executable) if executable.is_file() else args[0],
               'arguments': args[1:], 'timeout_seconds': timeout}
    for attempt in range(1, (retries if safe_retry else 0) + 2):
        start = time.monotonic()
        emit('tool_started', {**details, 'attempt': attempt})
        try:
            result = progress_run(args, timeout, progress) if progress else subprocess.run(args, capture_output=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            transient = isinstance(error, OSError) and error.errno in (errno.EAGAIN, errno.EINTR, errno.ETIMEDOUT)
            retry = safe_retry and transient and attempt <= retries
            emit('tool_failed', {**details, 'attempt': attempt, 'category': 'timeout' if isinstance(error, subprocess.TimeoutExpired) else 'transient' if transient else 'environment',
                                'error_type': type(error).__name__, 'retry': retry, 'elapsed': time.monotonic() - start})
            if retry:
                time.sleep(min(attempt, 2))
                continue
            block_failure({**details, 'error_type': type(error).__name__, 'attempt': attempt})
            raise
        emit('tool_completed' if result.returncode == 0 else 'tool_failed',
             {**details, 'attempt': attempt, 'returncode': result.returncode,
              'category': None if result.returncode == 0 else 'command_failure',
              'retry': False, 'elapsed': time.monotonic() - start})
        if result.returncode:
            block_failure({**details, 'returncode': result.returncode, 'attempt': attempt})
        return result


def operation(name, inputs, action):
    """Record stage execution; tool success is not editorial acceptance."""
    op = uuid.uuid4().hex
    details = {'operation': op, 'stage': name, 'inputs': inputs,
               'toolkit': identity(Path(__file__)), 'pipeline': identity(Path(__file__).with_name('pipeline.py')),
               'composition': identity(Path(__file__).with_name('composition.py'))}
    emit('stage_started', details)
    try:
        result = action()
    except Exception as error:
        emit('stage_failed', {**details, 'error_type': type(error).__name__,
                             'message': str(error)[-2000:], 'next_action': 'Inspect failure; reconcile artifacts before resuming'})
        block_failure({**details, 'error_type': type(error).__name__, 'message': str(error)[-2000:]})
        raise
    emit('stage_completed', {**details, 'result': result, 'editorial_review': 'not_established'})
    return result
