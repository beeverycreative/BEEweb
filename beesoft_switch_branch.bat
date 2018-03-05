@ECHO off

ECHO.
SET /P BRANCH="Please enter the BEEweb branch name you want to run: "

IF [%BRANCH%] == [] (
	ECHO.
	ECHO Invalid branch specified.
	EXIT /B
)

@ECHO on

cd %PROGRAMFILES(X86)%\BEESOFT4\BEEweb\
..\Git\bin\git.exe pull
..\Git\bin\git.exe checkout %BRANCH%

..\Python27\python.exe setup.py install

pause