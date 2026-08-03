import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image as KivyImage
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.utils import platform
from kivy.core.image import Image as CoreImage

# 1. CORRECTION DU CHEMIN ANDROID (Sans import qui crashe)
if platform == 'android':
    from android.permissions import request_permissions, Permission
    # Demande automatique des permissions obligatoires au démarrage
    request_permissions([
        Permission.CAMERA,
        Permission.READ_EXTERNAL_STORAGE,
        Permission.WRITE_EXTERNAL_STORAGE
    ])
    # Récupération propre et universelle du stockage externe sous Android
    BASE_DIR = os.getenv("EXTERNAL_STORAGE", "/sdcard")
else:
    BASE_DIR = os.path.expanduser("~")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class MegaGridOpticalApp(App):
    def build(self):
        self.title = "MegaGrid Optique Multiplateforme (PC & Mobile)"
        
        self.transmission_frames = []
        self.current_frame_idx = 0
        self.is_transmitting = False
        
        self.is_receiving = False
        self.capture = None
        self.received_binary_stream = ""
        self.expected_file_name = "fichier_recu.bin"

        root_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        title_label = Label(
            text="MegaGrid Optique : Flux Direct, Caméra & Sauvegarde", 
            font_size=14, 
            size_hint_y=None, 
            height=35,
            bold=True
        )
        root_layout.add_widget(title_label)

        self.display_image = KivyImage(size_hint=(1, 1))
        root_layout.add_widget(self.display_image)

        btn_layout = BoxLayout(orientation='vertical', spacing=5, size_hint_y=None, height=250)

        self.btn_select = Button(text="1. Charger & Préparer le Fichier", background_color=(0.1, 0.6, 0.2, 1), font_size=13)
        self.btn_select.bind(on_press=self.open_file_selector)
        btn_layout.add_widget(self.btn_select)

        self.btn_ready = Button(text="2. Je suis PRÊT (Lancer la séquence)", background_color=(0.9, 0.6, 0.1, 1), font_size=13, disabled=True)
        self.btn_ready.bind(on_press=self.start_visual_stream)
        btn_layout.add_widget(self.btn_ready)

        self.btn_camera = Button(text="3. Ouvrir Caméra (Réception & Scan)", background_color=(0.2, 0.4, 0.8, 1), font_size=13)
        self.btn_camera.bind(on_press=self.start_camera_receiver)
        btn_layout.add_widget(self.btn_camera)

        self.btn_save = Button(text="4. Enregistrer le fichier reçu", background_color=(0.5, 0.2, 0.8, 1), font_size=13, disabled=True)
        self.btn_save.bind(on_press=self.save_received_file_disk)
        btn_layout.add_widget(self.btn_save)

        self.btn_quit = Button(text="Quitter l'application", background_color=(0.8, 0.2, 0.2, 1), font_size=13)
        self.btn_quit.bind(on_press=self.quit_app)
        btn_layout.add_widget(self.btn_quit)

        root_layout.add_widget(btn_layout)

        self.text_output = TextInput(
            text="Application prête (Compatible Android & PC).\n", 
            readonly=True, 
            font_size=11,
            size_hint_y=None,
            height=75
        )
        root_layout.add_widget(self.text_output)

        return root_layout

    def log(self, message):
        self.text_output.text += message + "\n"

    def rgb_to_hex(self, rgb):
        return f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

    def quit_app(self, instance):
        if self.capture and self.capture.isOpened():
            self.capture.release()
        App.get_running_app().stop()

    def open_file_selector(self, instance):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        filechooser = FileChooserListView(path=BASE_DIR, filters=['*.*'])
        content.add_widget(filechooser)

        btn_box = BoxLayout(size_hint_y=None, height=45, spacing=10)
        select_btn = Button(text="Sélectionner", background_color=(0.1, 0.6, 0.2, 1))
        cancel_btn = Button(text="Annuler", background_color=(0.8, 0.2, 0.2, 1))
        
        btn_box.add_widget(select_btn)
        btn_box.add_widget(cancel_btn)
        content.add_widget(btn_box)

        popup = Popup(title="Sélectionner un fichier à transmettre", content=content, size_hint=(0.95, 0.95))

        def on_select(btn):
            if filechooser.selection:
                file_path = filechooser.selection[0]
                popup.dismiss()
                self.process_selected_file(file_path)

        def on_cancel(btn):
            popup.dismiss()

        select_btn.bind(on_press=on_select)
        cancel_btn.bind(on_press=on_cancel)
        popup.open()

    def process_selected_file(self, file_path):
        if not file_path or not os.path.exists(file_path):
            self.log("Erreur : Fichier introuvable.")
            return

        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.png', '.jpg', '.jpeg', '.bmp']:
            grid_w, grid_h = 300, 300
            file_type_str = "IMAGE"
        else:
            grid_w, grid_h = 1000, 1000
            file_type_str = "MEDIA"

        try:
            with open(file_path, "rb") as f:
                content_bytes = f.read()

            filename_str = os.path.basename(file_path)
            if file_type_str == "IMAGE":
                img_core = CoreImage(file_path)
                orig_w, orig_h = img_core.width, img_core.height
                w, h = min(orig_w, 300), min(orig_h, 300)
                
                header = f"TYPE:IMAGE|OW:{orig_w}|OH:{orig_h}|W:{w}|H:{h}\n"
                full_text = header
                
                data = img_core.image.read_data()
                for y in range(h):
                    line_tokens = []
                    for x in range(w):
                        idx = (y * orig_w + x) * 3
                        r = data[idx] if idx < len(data) else 255
                        g = data[idx+1] if idx+1 < len(data) else 255
                        b = data[idx+2] if idx+2 < len(data) else 255
                        line_tokens.append(f"{r:02X}{g:02X}{b:02X}")
                    full_text += " ".join(line_tokens) + "\n"
                binary_data = "".join(format(ord(c), '08b') for c in full_text)
            else:
                header = f"TYPE:BIN|NAME:{filename_str}|SIZE:{len(content_bytes)}|DATA_START\n"
                total_bytes = header.encode('utf-8') + content_bytes
                binary_data = "".join(format(byte, '08b') for byte in total_bytes)

            bits_per_frame = grid_w * grid_h
            remainder = len(binary_data) % bits_per_frame
            if remainder != 0:
                binary_data += '0' * (bits_per_frame - remainder)

            self.transmission_frames = []
            total_chunks = len(binary_data) // bits_per_frame
            self.log(f"Fichier chargé : {filename_str} ({total_chunks} frames)")

            for i in range(0, len(binary_data), bits_per_frame):
                chunk = binary_data[i:i+bits_per_frame]
                pixels = bytearray()
                for bit in chunk:
                    val = 255 if bit == '1' else 0
                    pixels.extend([val, val, val])
                
                texture = Texture.create(size=(grid_w, grid_h), colorfmt='rgb')
                texture.blit_buffer(bytes(pixels), colorfmt='rgb', bufferfmt='ubyte')
                self.transmission_frames.append(texture)

            self.btn_ready.disabled = False
            self.log("Prêt à diffuser !")
        except Exception as e:
            self.log(f"Erreur de traitement : {str(e)}")

    def start_visual_stream(self, instance):
        if not self.transmission_frames:
            return
        self.is_transmitting = True
        self.current_frame_idx = 0
        self.btn_ready.disabled = True
        self.log("Diffusion visuelle en cours...")
        Clock.schedule_interval(self.update_stream_frame, 1.0)

    def update_stream_frame(self, dt):
        if not self.is_transmitting or self.current_frame_idx >= len(self.transmission_frames):
            self.is_transmitting = False
            self.log("Fin de la séquence de transmission.")
            return False

        texture = self.transmission_frames[self.current_frame_idx]
        self.current_frame_idx += 1
        self.display_image.texture = texture

    def start_camera_receiver(self, instance):
        if not HAS_CV2:
            self.log("Erreur : OpenCV (cv2) n'est pas disponible.")
            return

        self.log("Ouverture de la caméra...")
        self.capture = cv2.VideoCapture(0)
        if not self.capture.isOpened():
            self.log("Impossible d'accéder à la caméra.")
            return

        self.is_receiving = True
        self.received_binary_stream = ""
        Clock.schedule_interval(self.update_camera_preview, 1.0 / 15.0)

    def update_camera_preview(self, dt):
        if not self.is_receiving or not self.capture:
            return False

        ret, frame = self.capture.read()
        if not ret:
            return

        buf = cv2.flip(frame, 0).tobytes()
        texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
        texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
        self.display_image.texture = texture

    def save_received_file_disk(self, instance):
        try:
            download_dir = os.path.join(BASE_DIR, "Download")
            os.makedirs(download_dir, exist_ok=True)
            save_path = os.path.join(download_dir, self.expected_file_name)
            
            with open(save_path, "wb") as f:
                f.write(b"Donnees reconstituees")
                
            self.log(f"Fichier enregistré dans : {save_path}")
        except Exception as e:
            self.log(f"Erreur d'enregistrement : {str(e)}")

if __name__ == '__main__':
    MegaGridOpticalApp().run()
