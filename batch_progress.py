"""Small progress snapshots; counters describe inputs, not upstream request counts."""

class BatchProgress:
    def __init__(self, callback, total):
        self.report = getattr(callback, 'report', lambda value: None)
        self.value = dict(total=total, processed=0, completed=0, failed=0, skipped=0,
                          notRequested=0, remaining=total, current=None)
        self.report(dict(self.value))

    def start(self, target):
        self.value['current'] = target
        self.report(dict(self.value))

    def finish(self, status):
        key = ('notRequested' if status == 'not_requested' else
               'failed' if status in ('error', 'invalid') else
               'skipped' if status == 'special_use' else 'completed')
        self.value[key] += 1
        self.value['processed'] = sum(self.value[k] for k in ('completed', 'failed', 'skipped'))
        self.value['remaining'] = self.value['total'] - self.value['processed']
        self.value['current'] = None
        self.report(dict(self.value))
