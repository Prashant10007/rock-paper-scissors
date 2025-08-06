from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
from collections import deque
import os
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

# Global state
waiting_players = deque()
active_games = {}
scores = {}
top_scorer = {"name": "", "score": 0}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def on_join(data):
    username = data['username']
    mode = data.get('mode', 'friend')  # 'friend' or 'computer'

    if username not in scores:
        scores[username] = 0
    update_top_scorer()

    if mode == 'computer':
        # Create a virtual game with the computer
        room = f"{username}_vs_computer"
        active_games[room] = {
            'players': [username, 'Computer'],
            'moves': {}
        }
        join_room(room)
        emit('start_game', {'room': room, 'opponent': 'Computer'}, room=room)
        return

    # Multiplayer: match with waiting player or wait
    if waiting_players:
        opponent = waiting_players.popleft()
        room = f"{username}_vs_{opponent}"
        active_games[room] = {
            'players': [username, opponent],
            'moves': {}
        }
        for player in active_games[room]['players']:
            join_room(room)
        emit('start_game', {'room': room, 'opponent': opponent}, room=room)
    else:
        waiting_players.append(username)
        emit('waiting', {'msg': 'Waiting for another player to join...'})

@socketio.on('play_move')
def on_play_move(data):
    username = data['username']
    room = data['room']
    move = data['move']

    game = active_games.get(room)
    if not game:
        return

    game['moves'][username] = move

    # If playing against the computer, make the move immediately
    if 'Computer' in game['players'] and 'Computer' not in game['moves']:
        game['moves']['Computer'] = random.choice(['r', 'p', 's'])

    if len(game['moves']) == 2:
        players = game['players']
        move1 = game['moves'][players[0]]
        move2 = game['moves'][players[1]]
        result = determine_result(move1, move2)

        # Update scores
        if result == 'draw':
            scores[players[0]] += 1
            if players[1] != 'Computer':
                scores[players[1]] += 1
        elif result == 'p1':
            scores[players[0]] += 2
        elif result == 'p2' and players[1] != 'Computer':
            scores[players[1]] += 2

        update_top_scorer()

        emit('result', {
            'players': players,
            'moves': [move1, move2],
            'winner': result,
            'scores': {
                players[0]: scores[players[0]],
                players[1]: scores[players[1]] if players[1] != 'Computer' else 'Bot'
            }
        }, room=room)

        del active_games[room]

# Helper function to determine round winner
def determine_result(p1, p2):
    mapping = {'r': 0, 'p': 1, 's': -1}
    you = mapping[p1]
    opponent = mapping[p2]

    if you == opponent:
        return 'draw'
    elif (opponent - you) == -1 or (opponent - you) == 2:
        return 'p1'
    elif (opponent - you) == 1 or (opponent - you) == -2:
        return 'p2'
    else:
        return 'error'

# Update top scorer for the entire platform
def update_top_scorer():
    global top_scorer
    if scores:
        top_name, top_score = max(scores.items(), key=lambda x: x[1])
        top_scorer = {"name": top_name, "score": top_score}
        socketio.emit('top_scorer', top_scorer)

# Run the app
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
