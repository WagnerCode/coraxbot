python3 bot.py &
python3 app.py &

sudo caddy reverse-proxy --from 176.109.104.88.sslip.io --to localhost:5000