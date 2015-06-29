#!/usr/bin/python

#Copyright (C) 2013 Pedro Manuel Baeza Romero

# Based on an script from Baptiste Saleil:
# https://github.com/bsaleil/rhythmbox-android-remote

#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.

import socket
import dbus
import sqlite3
import tempfile
import os
from gi.repository import GObject
from gi.repository import Peas
from gi.repository import RB
from gi.repository import Gio
import io
import rb

class RhythmboxAndroidRemotePlugin(GObject.GObject, Peas.Activatable):
    __gtype_name__ = 'RhythmboxAndroidRemotePlugin'
    object = GObject.property(type=GObject.GObject)

    def __init__(self):
        super(RhythmboxAndroidRemotePlugin, self).__init__()

    def do_activate (self):
        self.shell = self.object
        self.server = ServerSocket(self, self.shell, 8484)
        self.server.start()

    def do_deactivate(self):
        self.server.shutdown()
        self.server = None
        self.shell = None

class ServerSocket():
    
    def __init__(self, gobject, shell, port):
        self.gobject = gobject
        self.shell = shell
        self.player = self.shell.props.shell_player
        self.library = self.shell.props.library_source
        self.art_store = RB.ExtDB(name="album-art")
        self.pendingSockets = []
        # Server socket
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.settimeout(None)
        self.server_socket.bind(("", self.port))
        self.server_socket.setblocking(0)
        self.server_socket.listen(5)
        # Welcome prints
        print("RhythmboxAndroidRemotePlugin server is listening.")
        print("Port : " + str(self.port))

    def start(self):
        self.watch_id = GObject.io_add_watch(self.server_socket, GObject.IO_IN, self.listen)

    def art_store_request_cb(self, *args): #key, filename, data, entry):
        entry = args[-1]
        data = args[-2]
        filename = args[-3]
        print (filename)
        
        if len(self.pendingSockets):
            client_socket = self.pendingSockets[0]
            self.pendingSockets.remove(client_socket)
            if not filename:
                filename = rb.find_plugin_file(self.gobject, "nocover.png")
                
            coverfp = open(filename, "rb")
            client_socket.send(coverfp.read())
            coverfp.close()
            client_socket.close()

    def prepareSyncDb(self):
        # Get temporary file
        tempFile = tempfile.NamedTemporaryFile(delete=False)
        tempFile.close()
        db = sqlite3.connect(tempFile.name, detect_types = sqlite3.PARSE_DECLTYPES or sqlite3.PARSE_COLNAMES)
        db.text_factory = str
        cursor = db.cursor()
        # Create tables
        cursor.execute('CREATE TABLE CoreArtists (ArtistID INTEGER PRIMARY KEY, Name TEXT)')
        cursor.execute('CREATE TABLE CoreAlbums (AlbumID INTEGER PRIMARY KEY, Title TEXT, TitleLowered TEXT, ArtistName TEXT)')
        cursor.execute('CREATE TABLE CoreTracks (TrackID INTEGER PRIMARY KEY, Title TEXT, ArtistID INTEGER, AlbumID INTEGER, Uri TEXT, TrackNumber INTEGER)')
        db.commit()
        # Populate data
        numArtist = 0
        artists = {}
        reversedArtists = {}
        numAlbum = 0
        albums = {}
        tracks = {}
        for row in self.library.props.base_query_model:
            entry = row[0]
            artist = entry.get_string(RB.RhythmDBPropType.ARTIST)#.decode('utf-8')
            if not reversedArtists.get(artist):
                numArtist += 1
                reversedArtists[artist] = numArtist
                artists[numArtist] = artist
            artistId = reversedArtists[artist]
            #albumInfo = (entry.get_string(RB.RhythmDBPropType.ALBUM).decode('utf-8'), artistId)
            albumInfo = (entry.get_string(RB.RhythmDBPropType.ALBUM), artistId)
            if not albums.get(albumInfo):
                numAlbum += 1
                albums[albumInfo] = numAlbum
            albumId = albums[albumInfo]
            trackId = entry.get_ulong(RB.RhythmDBPropType.ENTRY_ID)
            tracks[trackId] = ( 
                #entry.get_string(RB.RhythmDBPropType.TITLE).decode('utf-8'),
                entry.get_string(RB.RhythmDBPropType.TITLE), 
                artistId, 
                albumId,
                #entry.get_string(RB.RhythmDBPropType.LOCATION).decode('utf-8'),
                entry.get_string(RB.RhythmDBPropType.LOCATION),
                entry.get_ulong(RB.RhythmDBPropType.TRACK_NUMBER),
                )
        # Save artists to DB
        for artistId, artist in artists.items():
            cursor.execute("INSERT INTO CoreArtists VALUES (?, ?)", (artistId, artist))
        db.commit()
        # Save albums to DB
        for albumInfo, albumId in albums.items():
            albumName = albumInfo[0]
            cursor.execute("INSERT INTO CoreAlbums VALUES (?, ?, ?, ?)", (albumId, albumName, albumName, artists[albumInfo[1]]))
        db.commit()
        # Save tracks to DB
        for trackId, trackInfo in tracks.items():
            cursor.execute("INSERT INTO CoreTracks VALUES (?, ?, ?, ?, ?, ?)", (trackId, trackInfo[0], trackInfo[1], trackInfo[2], trackInfo[3], trackInfo[4]))
        db.commit()        

        db.close()
        return tempFile.name

    def listen(self, source, cb):
        client_socket, address = self.server_socket.accept()
        self.client_socket = client_socket
        received = (client_socket.recv(512)).decode("utf-8")
        print(received)
        action, var = received.split('/')
        print(action)
        pendingResponse = False
        # Set new position
        if action == "test":
            client_socket.send(b"")
        elif action == "status":
            # See if there is nothing playing (on RB launch, for example)
            if not self.player.get_playing_entry():
                ret = "idle"
            else:
                ret = ("playing" if self.player.get_playing()[1] else "paused")
            client_socket.send(ret.encode())
        elif action == "seek":
            self.player.seek(int(var) - self.player.get_playing_time()[1]);
        elif action == "repeat":
            current_play_order = self.player.props.play_order
            if current_play_order == 'linear':
                play_order = 'linear-loop'
            elif current_play_order == 'shuffle':
                play_order = 'random-by-age-and-rating'
            elif current_play_order == 'linear-loop':
                play_order = 'linear'
            else:
                play_order = 'shuffle'
            Gio.Settings.new('org.gnome.rhythmbox.player').set_string("play-order", play_order)
            client_socket.send(b"all" if (play_order == 'linear-loop' or play_order == 'random-by-age-and-rating') else b"off")
        elif action == "shuffle":
            current_play_order = self.player.props.play_order
            if current_play_order == 'linear':
                play_order = 'shuffle'
            elif current_play_order == 'shuffle':
                play_order = 'linear'
            elif current_play_order == 'linear-loop':
                play_order = 'random-by-age-and-rating'
            else:
                play_order = 'linear-loop'
            Gio.Settings.new('org.gnome.rhythmbox.player').set_string("play-order", play_order)
            client_socket.send(b"song" if (play_order == 'shuffle' or play_order == 'random-by-age-and-rating') else b"off")
        elif action == "volumeUp":
            current = self.player.get_volume()[1]
            self.player.set_volume(current + 0.1)
        elif action == "volumeDown":
            current = self.player.get_volume()[1]
            self.player.set_volume(current - 0.1)
        elif action ==  "coverImage":
            entry = self.player.get_playing_entry()
            key = entry.create_ext_db_key (RB.RhythmDBPropType.ALBUM)
            self.art_store.request(key, self.art_store_request_cb, entry)
            pendingResponse = True
        elif action == "all": # All information about current song
            ret = ("playing" if self.player.get_playing()[1] else "paused")  + "/" # playing/paused
            entry = self.player.get_playing_entry()
            if entry:
                ret += entry.get_string(RB.RhythmDBPropType.ALBUM) + "/"
                ret += entry.get_string(RB.RhythmDBPropType.ARTIST) + "/"
                ret += entry.get_string(RB.RhythmDBPropType.TITLE) + "/"
                try:
                    ret += str(self.player.get_playing_time()[1]) + "/"
                except:
                    ret += "0" + "/"
                # This code is not working correctly, although is the best practice for get song length
                # In a practical way, player will always being playing a song when you ask for this
                # information, so it's not a real problem.
                #ret += entry.get_string(RB.RhythmDBPropType.DURATION) + "/"
                # Get it with this alternative hack
                ret += str(self.player.get_playing_song_duration()) + "/"
                # Always send a cover (maybe no cover image, but send it anyway)
                #TODO: Try to figure out how to know if a song has cover or not
                ret += "true"
            else:
                # There is no song playing
                ret += "/" + "/" + "/" + "/" + "/" + "false"
            client_socket.send(ret.encode())
        elif action == "prev":
            self.player.do_previous()
        elif action == "playPause":
            status = self.player.get_playing()[1]
            self.player.playpause(not status)
        elif action == "next":
            self.player.do_next()
        elif action == "sync":
            dbPath = self.prepareSyncDb()
            if dbPath:
                with open(dbPath, 'rb') as f:
                    #client_socket.send(f.read().encode())
                    client_socket.send(f.read())
                os.remove(dbPath)
        elif action == "play": # Play an specific track
            entry = None
            path = var.replace('*','/')
            print (path)
            for row in self.library.props.base_query_model:
                if row[0].get_string(RB.RhythmDBPropType.LOCATION) == path:
                    entry = row[0]
                    break
            if entry:
                print ("found")
                self.shell.props.queue_source.add_entry(entry, -1)
                # Check if there is only one entry in queue
                #if len(self.shell.props.queue_source) == 1:
                    #self.player.do_next()
        # See if the response is pending and act consequently
        if pendingResponse:
            self.pendingSockets.append(client_socket)
        else:
            client_socket.close()
        return True

    def shutdown(self):
        GObject.source_remove(self.watch_id)
        self.server_socket.shutdown(socket.SHUT_RDWR)
        self.server_socket.close()
        self.gobject = None
        self.shell = None
        self.player = None
        self.art_store = None
