#!/bin/bash

# Hiển thị màu sắc cho dễ nhìn
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}>>> Bắt đầu cài đặt các gói NPM...${NC}"
npm install set-cookie-parser colors hpack chalk@4 random-useragent header-generator user-agents axios

echo -e "\n${GREEN}>>> Bắt đầu cài đặt các thư viện Python...${NC}"
pip install python-telegram-bot pytz requests psutil

echo -e "\n${GREEN}>>> Kiểm tra phiên bản đã cài...${NC}"
npm list --depth=0
pip list | grep -E "python-telegram-bot|requests|psutil"

echo -e "\n${GREEN}[XONG] Tất cả đã sẵn sàng!${NC}"
