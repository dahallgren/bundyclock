from .ledgers import JsonOutput, TextOutput, BundyHttpRest
from .dbledger import SqLiteOutput

def get_ledger(**kwargs):
    output = kwargs.get('ledger_type')

    if 'sqlite' in output:
        filename = '{}.db'.format(kwargs.get('ledger_file').split('.')[0])
        return SqLiteOutput(filename)
    elif 'json' in output:
        filename = '{}.json'.format(kwargs.get('ledger_file').split('.')[0])
        return JsonOutput(filename)
    elif 'text' in output:
        filename = '{}.txt'.format(kwargs.get('ledger_file').split('.')[0])
        return TextOutput(filename)
    elif 'http-rest' in output:
        return BundyHttpRest(kwargs.get('url'))