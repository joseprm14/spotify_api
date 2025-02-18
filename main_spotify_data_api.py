from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import requests
from base64 import b64encode
import json
import time

load_dotenv() # Coge las variables de entorno de .env
app = FastAPI() # Inicia la API
spotify_id = os.getenv("SPOTIFY_ID")
spotify_secret = os.getenv("SPOTIFY_SECRET")
token = None
token_expiration = 0

# Genera un nuevo token de acceso a no ser que ya exista uno válido
def get_access_token():
    global token, token_expiration
    if token and time.time() < token_expiration:
        # Si ya hay un token que no ha caducado todavía, se devuelve este
        return token
    
    spotify_url = 'https://accounts.spotify.com/api/token'
    auth_header = b64encode(f"{spotify_id}:{spotify_secret}".encode()).decode()
    headers = {
        'Authorization': f'Basic {auth_header}',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = {'grant_type': 'client_credentials'}
    # Se solicita un nuevo token
    response = requests.post(spotify_url, headers=headers, data=data)
    
    response.raise_for_status
    
    token_data = response.json()
    new_token = token_data.get('access_token')
    expires_in = token_data.get('expires_in', 3600)
    token_expiration = time.time() + expires_in
    
    return new_token


class User(BaseModel):
    name: str
    email: str

class Spotify_id(BaseModel):
    id: str

JSON_PATH = 'users_spotify.json'

@app.get('/api/users')
def get_data():
    # Devuelve los datos de los usuarios almacenados en el fichero json
    try:
        with open(JSON_PATH, 'r') as file:
            user_list = json.load(file)
    except FileNotFoundError:
        user_list = []
    return {"Usuarios": user_list}

@app.get('/api/users/{email}')
def get_user(email: str):
    # Devuelve los datos de un usuario específico identificado por su email
    try:
        with open(JSON_PATH, 'r') as file:
            user_list = json.load(file)
    except FileNotFoundError:
        user_list = []
    for user in user_list:
        if user['email'] == email:
            return {"Usuario": user}
    return {"error": "Usuario no existente"}

@app.post('/api/users', status_code=201)
def add_user(user: User):
    # Registra un nuevo usuario a la base de datos
    try:
        with open(JSON_PATH, 'r') as file:
            user_list = json.load(file)
    except FileNotFoundError:
        user_list = []
    
    for u in user_list:
        if u['email'] == user.email:
            return {"error": "Usuario con este email ya existe"}

    user_list.append(
        {"name": user.name,
         "email": user.email,
         "songs": [],
         "artists": []
         }
    )

    with open(JSON_PATH, "w") as file:
        json.dump(user_list, file, indent=4)
    return {"message": "Usuario añadido", "user": user, }

@app.delete('/api/users/{email}', status_code=201)
def remove_user(email: str):
    try:
        with open(JSON_PATH, 'r') as file:
            user_list = json.load(file)
    except FileNotFoundError:
        user_list = []
    
    # Se comprueba si existe un usuario con ese email y si es asi se elimina
    user_found = False
    for user in user_list:
        if user['email'] == email:
            user_list.remove(user)
            user_found = True
            break
    
    if user_found:
        with open(JSON_PATH, "w") as file:
            json.dump(user_list, file, indent=4)
        return{'message': f'Usuario con email {email} eliminado con exito'}
    else:
        return{'message': f'Usuario con email {email} no encontrado'}

@app.put('/api/users/{email}', status_code=201)
def update_user(email: str, new_user: User):
    try:
        with open(JSON_PATH, 'r') as file:
            user_list = json.load(file)
    except FileNotFoundError:
        user_list = []
    
    # Se comprueba si existe un usuario con ese email y si es asi se cambia su nombre
    for user in user_list:
        if user['email'] == email:
            user['name'] = new_user.name
            user['email'] = new_user.email
            with open(JSON_PATH, "w") as file:
                json.dump(user_list, file, indent=4)
            return{'message': f'Usuario con email {email} actualizado con exito'}

    return{'message': f'Usuario con email {email} no encontrado'}


@app.get('/api/songs/search/{song}')
def search_song(song: str):
    # Esta función busca una canción a partir de unas keywords, devolviendo información de los 5 primeros resultados
    
    token = get_access_token()
    search_header = {
        'Authorization': f'Bearer {token}'
    }
    search_parameters = {
        'q': song,
        'type': 'track',
        'limit': 5
    }
    # URL de la API
    url = f"https://api.spotify.com/v1/search"
    response = requests.get(url, headers=search_header, params=search_parameters)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Unexpected error")
    
    track = response.json().get('tracks', {}).get('items', [])
    

    songs = []

    for item in track:
        # Para cada item se calcula su duración
        length_seconds = item['duration_ms'] / 1000
        length_minutes = int(length_seconds // 60)
        length_seconds = length_seconds % 60
        if length_seconds < 10:
            length = f'{length_minutes}:0{length_seconds:.0f}'
        else:
            length = f'{length_minutes}:{length_seconds:.0f}'

        # Esta será la información que se devolverá de cada canción
        songs.append(
            {'title': item['name'],
             'artist': item['artists'][0]['name'],
             'album': item['album']['name'],
             'length': length,
             'url': item['external_urls']['spotify'],
             'id': item['uri'].split(':')[2]
             }
        )
    
    return {"list of songs": songs}

@app.get('/api/songs/{id}')
def get_song(id: str):
    # Está función devuelve información de una canción a partir de su identificador de Spotify
    
    token = get_access_token()
    header = {
        'Authorization': f'Bearer {token}'
    }
    # URL de la API
    url = f"https://api.spotify.com/v1/tracks/{id}"
    response = requests.get(url, headers=header)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Unexpected error")
    
    track = response.json()
    
    if track:
        length_seconds = track['duration_ms'] / 1000
        length_minutes = int(length_seconds // 60)
        length_seconds = length_seconds % 60
        if length_seconds < 10:
            length = f'{length_minutes}:0{length_seconds:.0f}'
        else:
            length = f'{length_minutes}:{length_seconds:.0f}'
        song = {'title': track['name'],
                'artist': track['artists'][0]['name'],
                'album': track['album']['name'],
                'length': length,
                'url': track['external_urls']['spotify'],
                'id': track['uri'].split(':')[2]
                }
    else:
        return {"message": "Canción no encontrada"}

    return {"song": song}
  
@app.post('/api/users/songs/{email}', status_code=201)
def add_song(email: str, new_song: Spotify_id):
    # Esta función añade el identificador de una canción a la lista de favoritos de un usuario

    try:
        with open(JSON_PATH, 'r') as file:
            user_list = json.load(file)
    except FileNotFoundError:
        return {"message": "Base de datos no encontrada"}
    
    # Comprobar si la canción existe en Spotify
    so = get_song(new_song.id)
    if 'song' not in so:
        return {'message': f'Canción con id ${new_song.id} no encontrada'}
    
    for user in user_list:
        if user['email'] == email:
            # Comprobar si la cancion ya esta añadida
            for song in user['songs']:
                if song == new_song.id:
                    return {'message': f'Cancion {new_song.id} ya esta entre las favoritas del usuario {email}'}
            
            user['songs'].append(new_song.id)
            with open(JSON_PATH, "w") as file:
                json.dump(user_list, file, indent=4)
            return {'message': f'Cancion {new_song.id} añadida para el usuario {email}'}
    
    return {'message': f'Usuario no encontrado'}

@app.get('/api/artists/search/{artist}')
def search_artist(artist: str):
    # Esta función busca un artista a partir de unas keywords, devolviendo información de los 5 primeros resultados

    token = get_access_token()
    search_header = {
        'Authorization': f'Bearer {token}'
    }
    search_parameters = {
        'q': artist,
        'type': 'artist',
        'limit': 5
    }
    # URL de la API
    url = f"https://api.spotify.com/v1/search"
    response = requests.get(url, headers=search_header, params=search_parameters)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Unexpected error")
    
    results = response.json().get('artists', {}).get('items', [])
    

    artists = []

    for item in results:
        artists.append(
            {'name': item['name'],
             'genres': item['genres'],
             'url': item['external_urls']['spotify'],
             'id': item['uri'].split(':')[2]
             }
        )
    
    return {"list of artists": artists}

@app.get('/api/artists/{id}')
def get_artist(id: str):
    # Está función devuelve información de un artista a partir de su identificador de Spotify

    token = get_access_token()
    header = {
        'Authorization': f'Bearer {token}'
    }
    # URL of the API
    url = f"https://api.spotify.com/v1/artists/{id}"
    response = requests.get(url, headers=header)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Unexpected error")
    
    result = response.json()

    if result:
        artist = {
                'name': result['name'],
                'genres': result['genres'],
                'url': result['external_urls']['spotify'],
                'id': result['uri'].split(':')[2]
                }
    else:
        return {"message": "No se ha encontrado el artista"}
    
    return {"artist": artist}

@app.post('/api/users/artists/{email}', status_code=201)
def add_artist(email: str, new_artist: Spotify_id):
    # Esta función añade el identificador de un artista a la lista de favoritos de un usuario
    
    try:
        with open(JSON_PATH, 'r') as file:
            user_list = json.load(file)
    except FileNotFoundError:
        return {"message": "Base de datos no encontrada"}
    
    # Comprobar si el artista existe en Spotify
    ar = get_artist(new_artist.id)
    if 'artist' not in ar:
        return {'message': f'Artista con id ${new_artist.id} no encontrado'}
    
    for user in user_list:
        if user['email'] == email:
            # Comprobar si el artista ya esta añadido
            for artist in user['artists']:
                if artist == new_artist.id:
                    return {'message': f'Artista {new_artist.id} ya esta entre los favoritos del usuario {email}'}
            user['artists'].append(new_artist.id)
            with open(JSON_PATH, "w") as file:
                json.dump(user_list, file, indent=4)
            return {'message': f'Artista {new_artist.id} añadido para el usuario {email}'}
    
    return {'message': f'Usuario no encontrado'}

@app.get('/api/users/songs/{email}')
def view_user_songs(email: str):
    # Esta función devuelve información sobre las canciones favoritas de un usuario

    try:
        with open(JSON_PATH, 'r') as file:
            user_list = json.load(file)
    except FileNotFoundError:
        return {"message": "Base de datos no encontrada"}
    
    for user in user_list:
        if user['email'] == email:
            song_list = []
            for song in user['songs']:
                # Se reutiliza la función get_song para obtener la información de las canciones
                new_song = get_song(song)
                if new_song['song']:
                    song_list.append(new_song['song'])
            return {'lista de canciones': song_list}
    
    return {'message': f'Usuario no encontrado'}

@app.get('/api/users/artists/{email}')
def view_user_artists(email: str):
    try:
        with open(JSON_PATH, 'r') as file:
            user_list = json.load(file)
    except FileNotFoundError:
        return {"message": "Base de datos no encontrada"}
    
    for user in user_list:
        if user['email'] == email:
            artist_list = []
            for artist in user['artists']:
                # Se reutiliza la función get_artist para obtener la información de los artistas
                new_artist = get_artist(artist)
                if new_artist['artist']:
                    artist_list.append(new_artist['artist'])
            return {'lista de artistas': artist_list}
    
    return {'message': f'Usuario no encontrado'}

@app.delete('/api/users/songs/{email}')
def remove_user_song(email: str, song: Spotify_id):
    # Esta funcion elimina una cancion del listado de favoritas
    try:
        with open(JSON_PATH, 'r') as file:
            user_list = json.load(file)
    except FileNotFoundError:
        return {"message": "Base de datos no encontrada"}
    
    for user in user_list:
        if user['email'] == email:
            for existing_song in user['songs']:
                if existing_song == song.id:
                    user['songs'].remove(song.id)
                    with open(JSON_PATH, "w") as file:
                        json.dump(user_list, file, indent=4)
                    return {'message': f'Canción ${song.id} eliminada para el usuario ${email}'}
            return {'message': f'Canción ${song.id} no está entre las favoritas del usuario ${email}'}
    
    return {'message': f'Usuario no encontrado'}

@app.delete('/api/users/artists/{email}')
def remove_user_artist(email: str, artist: Spotify_id):
    # Esta funcion elimina una cancion del listado de favoritas
    try:
        with open(JSON_PATH, 'r') as file:
            user_list = json.load(file)
    except FileNotFoundError:
        return {"message": "Base de datos no encontrada"}
    
    for user in user_list:
        if user['email'] == email:
            for existing_artist in user['artists']:
                if existing_artist == artist.id:
                    user['artists'].remove(artist.id)
                    with open(JSON_PATH, "w") as file:
                        json.dump(user_list, file, indent=4)
                    return {'message': f'Artista ${artist.id} eliminado para el usuario ${email}'}
            return {'message': f'Arista ${artist.id} no está entre los favoritos del usuario ${email}'}
    
    return {'message': f'Usuario no encontrado'}