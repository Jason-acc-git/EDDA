#!/bin/bash

# 로그 디렉토리 생성
mkdir -p /Users/engineers/EDDA/admin_platform/logs

# 환경 변수 설정
export PYTHONIOENCODING=UTF-8
export LANG=ko_KR.UTF-8
export LC_ALL=ko_KR.UTF-8

# 애플리케이션 실행
cd /Users/engineers/EDDA/admin_platform
/Users/engineers/EDDA/venv_new/bin/python flask_app.py > /Users/engineers/EDDA/admin_platform/logs/app.log 2> /Users/engineers/EDDA/admin_platform/logs/error.log &
