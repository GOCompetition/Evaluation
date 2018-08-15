REM sample script to run evaluation in Windows

SET case_dir=.\examples\case2\
SET raw=%case_dir%case.raw
SET rop=%case_dir%case.rop
SET con=%case_dir%case.con
SET inl=%case_dir%case.inl
SET sol1=%case_dir%sol1.txt
SET sol2=%case_dir%sol2.txt
SET det=%case_dir%detail.csv

REM run it
python test.py %raw% %rop% %con% %inl% %sol1% %sol2% %det%
