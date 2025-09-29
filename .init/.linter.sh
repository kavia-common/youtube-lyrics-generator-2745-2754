#!/bin/bash
cd /home/kavia/workspace/code-generation/youtube-lyrics-generator-2745-2754/python_console_app
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

