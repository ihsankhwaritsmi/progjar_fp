import json
import uuid
from datetime import datetime

class HttpServer:
    def __init__(self, game_instance):
        self.game = game_instance
        self.sessions = {}

    def response(self, kode=404, message='Not Found', messagebody='', headers={}):
        tanggal = datetime.now().strftime('%c')
        resp = []
        resp.append(f"HTTP/1.1 {kode} {message}\r\n")
        resp.append(f"Date: {tanggal}\r\n")
        resp.append("Connection: close\r\n")
        resp.append("Server: JempolServer/1.0\r\n")
        resp.append("Content-Type: application/json\r\n")
        
        body_bytes = json.dumps(messagebody).encode('utf-8')
        resp.append(f"Content-Length: {len(body_bytes)}\r\n")
        
        for kk, vv in headers.items():
            resp.append(f"{kk}: {vv}\r\n")
        resp.append("\r\n")

        response_headers = "".join(resp)
        return response_headers.encode('utf-8') + body_bytes

    def proses(self, data):
        requests = data.split("\r\n")
        baris = requests[0]
        
        all_headers_list = [n for n in requests[1:] if n]
        all_headers = {}
        content_length = 0
        for header in all_headers_list:
            if ':' in header:
                key, value = header.split(':', 1)
                all_headers[key.strip()] = value.strip()
                if key.lower() == 'content-length':
                    content_length = int(value.strip())

        body_str = ""
        if '\r\n\r\n' in data:
            body_str = data.split('\r\n\r\n', 1)[1]

        j = baris.split(" ")
        try:
            method = j[0].upper().strip()
            object_address = j[1].strip()

            if method == 'GET':
                return self.http_get(object_address, all_headers)
            elif method == 'POST':
                return self.http_post(object_address, all_headers, body_str)
            else:
                return self.response(400, 'Bad Request', {'error': 'Unsupported method'})
        except IndexError:
            return self.response(400, 'Bad Request', {'error': 'Malformed request line'})

    def http_get(self, object_address, headers):
        if object_address == '/gamestate':
            player_id = headers.get("X-Player-ID")
            if not player_id:
                return self.response(400, 'Bad Request', {'error': 'X-Player-ID header is required'})
            
            state = self.game.get_state()
            return self.response(200, 'OK', state)
        else:
            return self.response(404, 'Not Found', {'error': f'Endpoint {object_address} not found'})

    def http_post(self, object_address, headers, body_str):
        try:
            payload = json.loads(body_str) if body_str else {}
        except json.JSONDecodeError:
            return self.response(400, 'Bad Request', {'error': 'Invalid JSON in request body'})

        if object_address == '/connect':
            username = payload.get("username")
            if not username:
                return self.response(400, 'Bad Request', {'error': 'Username is required'})
            
            player_id = f"player_{uuid.uuid4().hex[:6]}"
            
            join_result = self.game.add_player(player_id, username)
            if join_result.get("status") == "error":
                return self.response(409, 'Conflict', {'error': join_result["message"]})
            
            return self.response(200, 'OK', {'player_id': player_id, 'message': 'Welcome!'})

        elif object_address == '/action':
            player_id = headers.get("X-Player-ID")
            if not player_id:
                return self.response(401, 'Unauthorized', {'error': 'X-Player-ID header is required'})

            if player_id not in self.game.players:
                return self.response(404, 'Not Found', {'error': 'Player not found in game.'})
                
            self.game.handle_action(player_id, payload)
            return self.response(200, 'OK', {'status': 'Action received'})

        elif object_address == '/disconnect':
            player_id = headers.get("X-Player-ID")
            if not player_id:
                 return self.response(401, 'Unauthorized', {'error': 'X-Player-ID header is required'})
            self.game.remove_player(player_id)
            return self.response(200, 'OK', {'status': f'Player {player_id} disconnected'})
            
        else:
            return self.response(404, 'Not Found', {'error': f'Endpoint {object_address} not found'})
