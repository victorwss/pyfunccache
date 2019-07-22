pip install ./ --upgrade
mypy --disallow-untyped-defs --disallow-untyped-calls --disallow-incomplete-defs --check-untyped-defs --disallow-untyped-decorators --strict --show-traceback pyfunccache/memo.py pyfunccache/cache.py tests/cache_test.py tests/memo_test.py
pytest