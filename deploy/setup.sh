#!/bin/bash
# Oracle Free Tier Ubuntu 서버 초기 세팅 스크립트
# 실행: bash deploy/setup.sh

set -e

echo "=== 패키지 업데이트 ==="
sudo apt update && sudo apt upgrade -y

echo "=== PostgreSQL 설치 ==="
sudo apt install -y postgresql postgresql-contrib

echo "=== Python 환경 ==="
sudo apt install -y python3-pip python3-venv nginx

echo "=== DB 및 유저 생성 ==="
sudo -u postgres psql << SQL
CREATE USER suggestuser WITH PASSWORD 'your_password';
CREATE DATABASE suggestions OWNER suggestuser;
SQL

echo "=== 앱 디렉토리 세팅 ==="
cd /home/ubuntu/suggesting_new
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "=== .env 설정 ==="
cp .env.example .env
echo ">>> .env 파일을 열어 DATABASE_URL, JWT_SECRET_KEY 등을 수정하세요!"

echo "=== nginx 설정 ==="
sudo cp deploy/nginx.conf /etc/nginx/sites-available/suggesting
sudo ln -sf /etc/nginx/sites-available/suggesting /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

echo "=== systemd 서비스 등록 ==="
sudo cp deploy/suggesting.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable suggesting
sudo systemctl start suggesting

echo "=== 방화벽 설정 (Oracle 보안그룹에서도 80 열어야 함) ==="
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT

echo "=== 완료! ==="
echo "관리자 계정 생성: source venv/bin/activate && python scripts/create_admin.py --username admin --password 'your_password'"
