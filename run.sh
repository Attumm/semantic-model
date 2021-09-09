while true; do
#  ls -d *.py */*.py | entr -d python3 tests/one_to_one_tests.py -f
  ls -d *.py */*.py | entr -d python3 -m unittest discover tests/
done

