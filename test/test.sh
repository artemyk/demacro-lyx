#!/bin/bash
rm test.pdf
rm test2.pdf
python3 ../demacro.py -f test.lyx test2.lyx
/Applications/LyX.app/Contents/MacOS/lyx --export pdf test2.lyx
diff <(pdftotext -bbox test.pdf /dev/stdout) <(pdftotext -bbox test2.pdf /dev/stdout)

