while true; do
  ls -d *.py | entr -d python3 test.py
done

