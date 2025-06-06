import sqlite3
import os
import threading
import time 
from kivy.logger import Logger
from kivy.clock import Clock
from kivy.app import App 
from kivy.properties import BooleanProperty, StringProperty 
from kivy.event import EventDispatcher
from pathlib import Path 

import mutagen
import hashlib

from dad_player.constants import (
    DATABASE_NAME, SUPPORTED_AUDIO_EXTENSIONS, ART_THUMBNAIL_DIR,
    ALBUM_ART_GRID_SIZE, DB_TRACKS_TABLE, DB_ALBUMS_TABLE, DB_ARTISTS_TABLE
)
from dad_player.utils import generate_file_hash, sanitize_filename_for_cache
from .image_utils import resize_image_data 

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None


class LibraryManager(EventDispatcher):
    is_scanning = BooleanProperty(False)
    scan_progress_message = StringProperty("")

    def __init__(self, settings_manager, **kwargs):
        super().__init__(**kwargs) 
        self.settings_manager = settings_manager
        
        self.app_data_base_path = Path.home() / '.dad_player'
        os.makedirs(self.app_data_base_path, exist_ok=True)
        self.db_path = self.app_data_base_path / DATABASE_NAME
        
        self.art_cache_dir = self.app_data_base_path / "cache" / ART_THUMBNAIL_DIR
        os.makedirs(self.art_cache_dir, exist_ok=True)

        self._initialize_db() 
        
        self._scan_thread = None
        self._progress_callback = None 
        self._total_files_to_scan = 0
        self._files_scanned_so_far = 0
        Logger.info(f"LibraryManager: Initialized. DB at: {self.db_path}")

    def _get_db_connection(self):
        thread_id = threading.get_ident()
        try:
            conn = sqlite3.connect(self.db_path, timeout=10) 
            conn.row_factory = sqlite3.Row 
            return conn
        except sqlite3.Error as e:
            Logger.error(f"LibraryManager: Database connection error for thread {thread_id}: {e}")
            return None

    def _close_db_connection(self, conn, caller_info="Unknown"):
        if conn:
            thread_id = threading.get_ident()
            try:
                conn.close()
            except sqlite3.Error as e:
                Logger.error(f"LibraryManager: Error closing DB connection from {caller_info} in thread {thread_id}: {e}")

    def _initialize_db(self):
        # Ensure it creates 'filepath' and 'filehash' in DB_TRACKS_TABLE.
        Logger.info(f"LibraryManager: Initializing database at {self.db_path}...")
        conn = self._get_db_connection()
        if not conn: 
            Logger.error("LibraryManager: _initialize_db failed to get DB connection.")
            return
        cursor = None
        try:
            cursor = conn.cursor()
            # Create artists table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {DB_ARTISTS_TABLE} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL COLLATE NOCASE
                )
            """)
            # Create albums table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {DB_ALBUMS_TABLE} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL COLLATE NOCASE,
                    artist_id INTEGER,
                    art_filename TEXT,
                    year INTEGER,
                    UNIQUE(name, artist_id),
                    FOREIGN KEY (artist_id) REFERENCES {DB_ARTISTS_TABLE}(id) ON DELETE CASCADE 
                )
            """)
            # Create tracks table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {DB_TRACKS_TABLE} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filepath TEXT UNIQUE NOT NULL,
                    filehash TEXT,
                    title TEXT COLLATE NOCASE,
                    album_id INTEGER,
                    artist_id INTEGER,
                    track_number INTEGER,
                    disc_number INTEGER,
                    duration REAL,
                    genre TEXT COLLATE NOCASE,
                    year INTEGER,
                    last_modified REAL,
                    FOREIGN KEY (album_id) REFERENCES {DB_ALBUMS_TABLE}(id) ON DELETE SET NULL,
                    FOREIGN KEY (artist_id) REFERENCES {DB_ARTISTS_TABLE}(id) ON DELETE SET NULL
                )
            """)
            
            cursor.execute(f"PRAGMA table_info({DB_TRACKS_TABLE})")
            columns_info = cursor.fetchall()
            column_names = [col_info['name'] for col_info in columns_info]
            Logger.info(f"LibraryManager: Columns in {DB_TRACKS_TABLE}: {column_names}")

            if 'filepath' not in column_names:
                Logger.critical(f"LibraryManager: CRITICAL - 'filepath' column MISSING from {DB_TRACKS_TABLE} after CREATE TABLE!")
            
            if 'filehash' not in column_names:
                Logger.info(f"LibraryManager: Adding 'filehash' column to {DB_TRACKS_TABLE} as it's missing.")
                cursor.execute(f"ALTER TABLE {DB_TRACKS_TABLE} ADD COLUMN filehash TEXT")
            
            conn.commit()
            Logger.info("LibraryManager: Database initialized/schema verified successfully.")
        except sqlite3.Error as e:
            Logger.error(f"LibraryManager: Database schema initialization error: {e}")
            if conn: conn.rollback()
        finally:
            if cursor:
                cursor.close()
            self._close_db_connection(conn, "_initialize_db")


    def _get_or_create_artist_id(self, cursor, artist_name):
        if not artist_name or not artist_name.strip(): return None
        artist_name = artist_name.strip()
        cursor.execute(f"SELECT id FROM {DB_ARTISTS_TABLE} WHERE name = ?", (artist_name,))
        row = cursor.fetchone()
        if row: return row['id']
        try:
            cursor.execute(f"INSERT INTO {DB_ARTISTS_TABLE} (name) VALUES (?)", (artist_name,))
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            cursor.execute(f"SELECT id FROM {DB_ARTISTS_TABLE} WHERE name = ?", (artist_name,))
            row = cursor.fetchone()
            return row['id'] if row else None

    def _get_or_create_album_id(self, cursor, album_name, album_artist_id, year=None):
        if not album_name or not album_name.strip(): return None
        album_name = album_name.strip()
        # Standardize query for album lookup
        query = f"SELECT id FROM {DB_ALBUMS_TABLE} WHERE name = ? AND "
        params = [album_name]
        if album_artist_id is not None:
            query += "artist_id = ?"
            params.append(album_artist_id)
        else:
            query += "artist_id IS NULL"
        
        cursor.execute(query, tuple(params))
        row = cursor.fetchone()
        if row: return row['id']
        try:
            cursor.execute(f"INSERT INTO {DB_ALBUMS_TABLE} (name, artist_id, year) VALUES (?, ?, ?)", (album_name, album_artist_id, year))
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            cursor.execute(query, tuple(params))
            row = cursor.fetchone()
            return row['id'] if row else None

    def _cache_album_art(self, raw_art_data, album_id, album_name):

        if not raw_art_data or not PILImage: return None
        

        resized_stream = resize_image_data(raw_art_data, target_max_dim=ALBUM_ART_GRID_SIZE, output_format="WEBP", quality=80) 
        file_ext = ".webp"
        if not resized_stream:
             resized_stream = resize_image_data(raw_art_data, target_max_dim=ALBUM_ART_GRID_SIZE, output_format="PNG") 
             file_ext = ".png"

        if resized_stream:
            sanitized_album_name = sanitize_filename_for_cache(album_name if album_name else "unknown_album")
            name_hash = hashlib.md5(f"{album_id}_{sanitized_album_name}".encode()).hexdigest()[:10]
            art_filename = f"art_{name_hash}{file_ext}"
            art_filepath = self.art_cache_dir / art_filename 
            try:
                with open(art_filepath, 'wb') as f:
                    f.write(resized_stream.getvalue())
                Logger.info(f"LibraryManager: Cached album art to {art_filepath}")
                return art_filename 
            except IOError as e:
                Logger.error(f"LibraryManager: Error writing cached album art {art_filepath}: {e}")
        return None

    def _process_file_metadata(self, filepath, conn): 
        cursor = None
        try:
            cursor = conn.cursor() # Use the provided connection's cursor
            file_stat = os.stat(filepath)
            last_modified = file_stat.st_mtime
            current_file_hash = generate_file_hash(filepath)

            # Check if track exists and if it needs update
            cursor.execute(f"SELECT id, last_modified, filehash FROM {DB_TRACKS_TABLE} WHERE filepath = ?", (filepath,))
            existing_track = cursor.fetchone()

            if existing_track and existing_track['last_modified'] == last_modified and existing_track['filehash'] == current_file_hash:
                # Logger.debug(f"LibraryManager: Track {filepath} is up-to-date.")
                return False

            audio = mutagen.File(filepath, easy=True) 
            if not audio:
                Logger.warning(f"LibraryManager: Could not read metadata for: {filepath}")
                return False

            # Extract common tags, providing defaults
            title = str(audio.get('title', [os.path.splitext(os.path.basename(filepath))[0]])[0]) if audio.get('title') else os.path.splitext(os.path.basename(filepath))[0]
            artist = str(audio.get('artist', ['Unknown Artist'])[0]) if audio.get('artist') else "Unknown Artist"
            album = str(audio.get('album', ['Unknown Album'])[0]) if audio.get('album') else "Unknown Album"
            albumartist = str(audio.get('albumartist', [artist])[0]) if audio.get('albumartist') else artist
            
            track_num_str = str(audio.get('tracknumber', ['0'])[0]).split('/')[0] if audio.get('tracknumber') else '0'
            disc_num_str = str(audio.get('discnumber', ['0'])[0]).split('/')[0] if audio.get('discnumber') else '0'
            track_num = int(track_num_str) if track_num_str.isdigit() else None
            disc_num = int(disc_num_str) if disc_num_str.isdigit() else None

            genre = str(audio.get('genre', [''])[0]) if audio.get('genre') else None
            date_str = str(audio.get('date', [audio.get('originaldate', [''])[0]])[0]) if audio.get('date') or audio.get('originaldate') else None
            year = None
            if date_str:
                if len(date_str) >= 4 and date_str[:4].isdigit(): year = int(date_str[:4])
                elif date_str.isdigit() and len(date_str) == 4 : year = int(date_str)

            duration = audio.info.length if hasattr(audio, 'info') and hasattr(audio.info, 'length') else 0.0

            # Get/Create IDs for artist and album
            track_artist_id = self._get_or_create_artist_id(cursor, artist)
            album_artist_id_for_album_table = self._get_or_create_artist_id(cursor, albumartist)
            album_id = self._get_or_create_album_id(cursor, album, album_artist_id_for_album_table, year)

            # Process album art
            art_filename = None
            if album_id:
                cursor.execute(f"SELECT art_filename FROM {DB_ALBUMS_TABLE} WHERE id = ?", (album_id,))
                album_row = cursor.fetchone()
                if album_row and not album_row['art_filename']:
                    raw_art_data = None
                    try:
                        # Attempt to get embedded art (more comprehensive checks)
                        detailed_audio = mutagen.File(filepath)
                        if detailed_audio:
                            if 'APIC:' in detailed_audio:
                                raw_art_data = detailed_audio['APIC:'].data
                            elif hasattr(detailed_audio, 'pictures') and detailed_audio.pictures:
                                raw_art_data = detailed_audio.pictures[0].data
                            elif 'metadata_block_picture' in detailed_audio:
                                pic_data_b64_list = detailed_audio.get('metadata_block_picture')
                                if pic_data_b64_list:
                                    import base64
                                    pic_data_b64 = pic_data_b64_list[0]
                                    raw_art_data = base64.b64decode(pic_data_b64.split('|')[-1] if isinstance(pic_data_b64, str) and '|' in pic_data_b64 else pic_data_b64)
                        
                        if raw_art_data:
                            art_filename = self._cache_album_art(raw_art_data, album_id, album)
                            if art_filename:
                                cursor.execute(f"UPDATE {DB_ALBUMS_TABLE} SET art_filename = ? WHERE id = ?", (art_filename, album_id))
                    except Exception as e_art:
                        Logger.warning(f"LibraryManager: Error extracting/caching art for {filepath}: {e_art}")
                elif album_row:
                    art_filename = album_row['art_filename']
            
            if existing_track:
                track_data_tuple_update = (
                    current_file_hash, title, album_id, track_artist_id, track_num, 
                    disc_num, duration, genre, year, last_modified, existing_track['id'] 
                )
                cursor.execute(f"""UPDATE {DB_TRACKS_TABLE} SET 
                                filehash=?, title=?, album_id=?, artist_id=?, track_number=?, 
                                disc_number=?, duration=?, genre=?, year=?, last_modified=? 
                                WHERE id=?""", track_data_tuple_update)
            else:
                track_data_tuple_insert = (
                    filepath, current_file_hash, title, album_id, track_artist_id, 
                    track_num, disc_num, duration, genre, year, last_modified
                )
                cursor.execute(f"""INSERT INTO {DB_TRACKS_TABLE} 
                                (filepath, filehash, title, album_id, artist_id, track_number, 
                                disc_number, duration, genre, year, last_modified) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", track_data_tuple_insert)
            # conn.commit() # Commit is handled by the calling thread function after a batch
            return True
        except mutagen.MutagenError as e:
            Logger.warning(f"LibraryManager: Mutagen error for {filepath}: {e}")
        except sqlite3.Error as e:
            Logger.error(f"LibraryManager: DB error processing file {filepath}: {e}")
        except AttributeError as e:
            Logger.warning(f"LibraryManager: Attribute error processing metadata for {filepath}: {e}")
        except Exception as e:
            Logger.error(f"LibraryManager: Unexpected error processing file {filepath}: {e}")
            import traceback; traceback.print_exc()
        finally:
            if cursor:
                cursor.close() 
        return False

    def _scan_music_folders_thread_target(self, music_folders, full_rescan=False):
        scan_thread_id = threading.get_ident()
        Logger.critical(f"LibraryManager: SCAN THREAD {scan_thread_id} STARTED. Folders to scan: {music_folders}")

        self._files_scanned_so_far = 0
        self._total_files_to_scan = 0
        files_processed_this_scan = 0

        # --- Phase 1: Count total files to scan ---
        if self._progress_callback:
            # Use setattr for Kivy properties when called from Clock schedule
            Clock.schedule_once(lambda dt: setattr(self, 'scan_progress_message', "Calculating total files..."))

        if not self.is_scanning: # Check if scan was cancelled very early
            Logger.info("LibraryManager: Scan was externally cancelled right after thread start (before counting).")
            if self._progress_callback:
                Clock.schedule_once(lambda dt: setattr(self, 'scan_progress_message', "Scan cancelled."))
                Clock.schedule_once(lambda dt: self._progress_callback(0, self.scan_progress_message, True))
            Clock.schedule_once(lambda dt: setattr(self, 'is_scanning', False)) # Ensure flag is reset
            return

        for folder_path_idx, folder_path in enumerate(music_folders):
            if not self.is_scanning:
                Logger.info(f"LibraryManager: Scan cancelled during file counting (folder {folder_path_idx+1}).")
                break 
            Logger.info(f"LibraryManager: >>> Counting in folder: '{folder_path}' (Exists: {os.path.exists(folder_path)}, IsDir: {os.path.isdir(folder_path)})")
            if not os.path.isdir(folder_path):
                Logger.warning(f"LibraryManager: Skipping invalid folder path during count: {folder_path}")
                continue
            for root, _, files in os.walk(folder_path):
                if not self.is_scanning:
                    Logger.info(f"LibraryManager: Scan cancelled during os.walk (count) in '{root}'.")
                    break
                for filename in files:
                    if not self.is_scanning:
                        Logger.info(f"LibraryManager: Scan cancelled while counting files in '{root}'.")
                        break
                    if filename.lower().endswith(SUPPORTED_AUDIO_EXTENSIONS):
                        # Logger.info(f"LibraryManager: FOUND SUPPORTED AUDIO FILE (for count): {os.path.join(root, filename)}") # Already logged by main scan
                        self._total_files_to_scan += 1
                if not self.is_scanning: break 
            if not self.is_scanning: break 
        
        if not self.is_scanning : # If cancelled during counting phase
            Logger.info("LibraryManager: Scan cancelled after (or during) file counting phase.")
            return 

        if self._total_files_to_scan == 0: # No files found to scan
            final_message = "No music files found in selected folders."
            Logger.info(f"LibraryManager: {final_message}")
            Clock.schedule_once(lambda dt: setattr(self, 'is_scanning', False))
            Clock.schedule_once(lambda dt, msg=final_message: setattr(self, 'scan_progress_message', msg))
            if self._progress_callback:
                Clock.schedule_once(lambda dt, msg=final_message: self._progress_callback(1.0, msg, True))
            return
        else: # Files found, update progress message
            initial_scan_msg = f"Found {self._total_files_to_scan} files to scan. Processing..."
            Logger.info(f"LibraryManager: {initial_scan_msg}")
            Clock.schedule_once(lambda dt, msg=initial_scan_msg: setattr(self, 'scan_progress_message', msg))
            if self._progress_callback:
                Clock.schedule_once(lambda dt: self._progress_callback(0, self.scan_progress_message, False))
        
        # --- Phase 2: Process files and update database ---
        conn = self._get_db_connection() 
        if not conn:
            Clock.schedule_once(lambda dt: setattr(self, 'scan_progress_message', "Scan failed: DB Connection Error"))
            if self._progress_callback:
                Clock.schedule_once(lambda dt: self._progress_callback(1.0, self.scan_progress_message, True))
            Clock.schedule_once(lambda dt: setattr(self, 'is_scanning', False))
            return

        try:
            all_filepaths_in_scan = [] # For full rescan, to find obsolete tracks
            self._files_scanned_so_far = 0 # Reset for actual processing count

            for folder_idx, folder_path in enumerate(music_folders):
                if not self.is_scanning: break 
                Logger.info(f"LibraryManager: Processing folder content ({folder_idx+1}/{len(music_folders)}): {folder_path}")
                if not os.path.isdir(folder_path):
                    Logger.warning(f"LibraryManager: Skipping invalid folder path during processing: {folder_path}")
                    continue

                for root, _, files in os.walk(folder_path):
                    if not self.is_scanning: break
                    for filename in files:
                        if not self.is_scanning: break
                        if filename.lower().endswith(SUPPORTED_AUDIO_EXTENSIONS):
                            Logger.info(f"LibraryManager: FOUND SUPPORTED AUDIO FILE (for processing): {os.path.join(root, filename)}")
                            filepath = os.path.join(root, filename)
                            all_filepaths_in_scan.append(filepath) # Add to list for obsolete check
                            
                            if self._process_file_metadata(filepath, conn): 
                                files_processed_this_scan +=1 
                            
                            self._files_scanned_so_far += 1 # Increment for each supported file encountered for processing attempt

                            # Update progress every N files
                            if self._progress_callback and self._files_scanned_so_far % 10 == 0 : # Update more frequently
                                progress = self._files_scanned_so_far / self._total_files_to_scan if self._total_files_to_scan > 0 else 0
                                current_msg = f"Scanned: {self._files_scanned_so_far}/{self._total_files_to_scan} files..."
                                Clock.schedule_once(lambda dt, m=current_msg: setattr(self, 'scan_progress_message', m))
                                Clock.schedule_once(lambda dt, p=progress, m=current_msg: self._progress_callback(p, m, False))
                    if not self.is_scanning: break
                if self.is_scanning: conn.commit() # Commit after each folder
                else: break # If scan cancelled, break outer loop
            
            if self.is_scanning: conn.commit() # Final commit for any remaining operations

            # --- Phase 3: Full Rescan - Remove obsolete tracks ---
            if full_rescan and self.is_scanning: 
                Logger.info("LibraryManager: Full rescan - checking for obsolete tracks...")
                cursor = conn.cursor() 
                try:
                    cursor.execute(f"SELECT id, filepath FROM {DB_TRACKS_TABLE}")
                    db_tracks = cursor.fetchall()
                    # Efficiently find obsolete tracks: tracks in DB but not in current scan
                    db_filepaths = {track['filepath']: track['id'] for track in db_tracks}
                    scanned_filepaths_set = set(all_filepaths_in_scan)
                    
                    obsolete_track_ids = [
                        db_filepaths[fp] for fp in db_filepaths if fp not in scanned_filepaths_set
                    ]
                    
                    if obsolete_track_ids:
                        placeholders = ','.join('?' for _ in obsolete_track_ids)
                        cursor.execute(f"DELETE FROM {DB_TRACKS_TABLE} WHERE id IN ({placeholders})", obsolete_track_ids)
                        conn.commit()
                        Logger.info(f"LibraryManager: Removed {len(obsolete_track_ids)} obsolete tracks from DB.")
                except sqlite3.Error as e_obs:
                    Logger.error(f"LibraryManager: Error during obsolete track removal: {e_obs}")
                    if conn: conn.rollback()
                finally:
                    if cursor: cursor.close()

        except Exception as e: # Catch-all for unexpected errors during processing
            Logger.error(f"LibraryManager: Error during scan thread's main processing loop ({scan_thread_id}): {e}")
            import traceback; traceback.print_exc()
            if conn: conn.rollback() # Rollback on major error
        finally:
            self._close_db_connection(conn, f"_scan_music_folders_thread_target (Thread {scan_thread_id})")
            
            # Determine final message based on whether scan was cancelled or completed
            if not self.is_scanning: # If scan was cancelled at any point
                final_message = f"Scan cancelled. Found: {self._files_scanned_so_far} of {self._total_files_to_scan}. Processed in DB: {files_processed_this_scan}."
            else: # Scan completed naturally
                final_message = f"Scan complete. Processed: {files_processed_this_scan} of {self._total_files_to_scan} files."

            Clock.schedule_once(lambda dt: setattr(self, 'is_scanning', False)) # Ensure is_scanning is False
            Clock.schedule_once(lambda dt, msg=final_message: setattr(self, 'scan_progress_message', msg))
            Logger.info(f"LibraryManager: {final_message}")
            if self._progress_callback:
                 Clock.schedule_once(lambda dt, msg=final_message: self._progress_callback(1.0, msg, True))


    def start_scan_music_library(self, progress_callback=None, full_rescan=False):
        if self.is_scanning:
            Logger.info("LibraryManager: Scan already in progress.")
            if progress_callback: 
                # Provide current status if already scanning
                current_msg = self.scan_progress_message or "Scan already in progress."
                progress_val = self._files_scanned_so_far / self._total_files_to_scan if self._total_files_to_scan > 0 else 0
                progress_callback(progress_val, current_msg, False) # False because it's ongoing
            return False

        music_folders = self.settings_manager.get_music_folders()
        if not music_folders:
            Logger.info("LibraryManager: No music folders configured to scan.")
            if progress_callback: progress_callback(1.0, "No music folders configured.", True) # True because it's done (nothing to do)
            return False

        self._progress_callback = progress_callback
        self._files_scanned_so_far = 0 # Reset counters for new scan
        self._total_files_to_scan = 0 
        self.scan_progress_message = "Initializing scan..." # Initial message
        
        self.is_scanning = True # Set is_scanning to True before starting the thread

        self._scan_thread = threading.Thread(
            target=self._scan_music_folders_thread_target,
            args=(music_folders, full_rescan),
            daemon=True # So thread exits when main app exits
        )
        self._scan_thread.start()
        Logger.info(f"LibraryManager: Scan thread initiated. is_scanning = {self.is_scanning}")
        return True

    def stop_scan_music_library(self):
        if self.is_scanning and self._scan_thread and self._scan_thread.is_alive():
            Logger.info("LibraryManager: Attempting to stop library scan...")
            self.is_scanning = False # Signal thread to stop
        else:
            Logger.info("LibraryManager: No active scan in progress to stop or thread already finished.")
            self.is_scanning = False # Ensure it's false if called when not scanning

    # --- Data Retrieval Methods (Ensure they use their own connections) ---
    def get_all_artists(self):
        conn = self._get_db_connection()
        if not conn: return []
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT id, name FROM {DB_ARTISTS_TABLE} ORDER BY name COLLATE NOCASE")
            return [{"id": row["id"], "name": row["name"]} for row in cursor.fetchall()]
        except sqlite3.Error as e:
            Logger.error(f"LibraryManager: Error fetching artists: {e}")
            return []
        finally:
            if cursor: cursor.close()
            self._close_db_connection(conn, "get_all_artists")

    def get_albums_by_artist(self, artist_id=None): 
        conn = self._get_db_connection()
        if not conn: return []
        cursor = None
        try:
            cursor = conn.cursor()
            query = f"""
                SELECT al.id, al.name, al.year, al.art_filename, ar.name as artist_name
                FROM {DB_ALBUMS_TABLE} al
                LEFT JOIN {DB_ARTISTS_TABLE} ar ON al.artist_id = ar.id
            """
            params = []
            if artist_id is not None:
                query += " WHERE al.artist_id = ?"
                params.append(artist_id)
            query += " ORDER BY al.name COLLATE NOCASE" # Ensure consistent ordering
            
            cursor.execute(query, tuple(params))
            albums = []
            for row in cursor.fetchall():
                art_full_path = self.art_cache_dir / row["art_filename"] if row["art_filename"] else None
                albums.append({
                    "id": row["id"], "name": row["name"], 
                    "artist_name": row["artist_name"] or "Various Artists", # Handle null artist names
                    "year": row["year"],
                    "art_path": str(art_full_path) if art_full_path and art_full_path.exists() else None
                })
            return albums
        except sqlite3.Error as e:
            Logger.error(f"LibraryManager: Error fetching albums: {e}")
            return []
        finally:
            if cursor: cursor.close()
            self._close_db_connection(conn, "get_albums_by_artist")

    def get_tracks_by_album(self, album_id):
        conn = self._get_db_connection()
        if not conn: return []
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT t.id, t.filepath, t.title, t.track_number, t.disc_number, t.duration, ar.name as artist_name
                FROM {DB_TRACKS_TABLE} t
                LEFT JOIN {DB_ARTISTS_TABLE} ar ON t.artist_id = ar.id
                WHERE t.album_id = ?
                ORDER BY t.disc_number, t.track_number, t.title COLLATE NOCASE
            """, (album_id,))
            return [dict(row) for row in cursor.fetchall()] # Convert rows to dicts
        except sqlite3.Error as e:
            Logger.error(f"LibraryManager: Error fetching tracks for album {album_id}: {e}")
            return []
        finally:
            if cursor: cursor.close()
            self._close_db_connection(conn, "get_tracks_by_album")
            
    def get_track_details_by_filepath(self, filepath):
        conn = self._get_db_connection()
        if not conn: return None
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT t.id, t.filepath, t.title, t.duration, t.track_number, t.disc_number,
                       al.name as album, ar.name as artist, al.id as album_id
                FROM {DB_TRACKS_TABLE} t
                LEFT JOIN {DB_ALBUMS_TABLE} al ON t.album_id = al.id
                LEFT JOIN {DB_ARTISTS_TABLE} ar ON t.artist_id = ar.id
                WHERE t.filepath = ?
            """, (filepath,))
            row = cursor.fetchone()
            return dict(row) if row else None # Convert row to dict
        except sqlite3.Error as e:
            Logger.error(f"LibraryManager: Error fetching track details for {filepath}: {e}")
            return None
        finally:
            if cursor: cursor.close()
            self._close_db_connection(conn, "get_track_details_by_filepath")
            
    def get_album_art_path_for_file(self, filepath):
        conn = self._get_db_connection()
        if not conn: return None
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT al.art_filename
                FROM {DB_TRACKS_TABLE} t
                JOIN {DB_ALBUMS_TABLE} al ON t.album_id = al.id
                WHERE t.filepath = ? AND al.art_filename IS NOT NULL
            """, (filepath,))
            row = cursor.fetchone()
            if row and row['art_filename']:
                full_path = self.art_cache_dir / row['art_filename']
                return str(full_path) if full_path.exists() else None
            return None
        except sqlite3.Error as e:
            Logger.error(f"LibraryManager: Error fetching album art path for file {filepath}: {e}")
            return None
        finally:
            if cursor: cursor.close()
            self._close_db_connection(conn, "get_album_art_path_for_file")

    def get_track_filepath(self, track_id): 
        conn = self._get_db_connection()
        if not conn: return None
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT filepath FROM {DB_TRACKS_TABLE} WHERE id = ?", (track_id,))
            row = cursor.fetchone()
            return row['filepath'] if row else None
        except sqlite3.Error as e:
            Logger.error(f"LibraryManager: Error fetching filepath for track {track_id}: {e}")
            return None
        finally:
            if cursor: cursor.close()
            self._close_db_connection(conn, "get_track_filepath")

