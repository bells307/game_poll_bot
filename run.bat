docker build -t game_poll_bot .
docker run --name game_poll_bot -d --rm -v %cd%:/bot game_poll_bot