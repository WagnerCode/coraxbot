python3 bot.py &
python3 app.py &

sudo caddy reverse-proxy --from 176.123.163.57.sslip.io --to localhost:5000