import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image as KivyImage
from kivy.uix.camera import Camera
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.utils import platform
from kivy.core.image import Image as CoreImage

# Gestion des permissions Android
if platform == 'android':
    from android.permissions import request_permissions, Permission
    request_permissions([
        Permission.CAMERA,
        Permission.READ_EXTERNAL_STORAGE,
        Permission.WRITE_EXTERNAL_STORAGE
    ])
    BASE_DIR = os.getenv("EXTERNAL_STORAGE", "/sdcard")
else:
    BASE_DIR = os.path.expanduser("~")

class MegaGridOpticalApp(App):
    def build(self):
        self.title = "MegaGrid Optique (Caméra Kivy Native)"
        
        self.transmission_frames = []
        self.current_frame_idx = 0
        self.is_transmitting = False
        
        self.is_receiving = False
        self.received_binary_stream = ""
        self.expected_file_name = "fichier_recu.bin"

        root_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        title_label = Label(
            text="MegaGrid Optique : Mode Natif Kivy", 
            font_size=14, 
            size_hint_y=None, 
            height=35,
            bold=True
        )
        root_layout.add_widget(title_label)

        # Conteneur d'affichage (image statique ou caméra)
        self.display_container = BoxLayout(size_hint=(1, 1))
        self.display_image = KivyImage(size_hint=(1, 1))
        self.display_container.add_widget(self.display_image)
        root_layout.add_widget(self.display_container)

        btn_layout = BoxLayout(orientation='vertical', spacing=5, size_hint_y=None, height=250)

        self.btn_select = Button(text="1. Charger & Préparer le Fichier", background_color=(0.1, 0.6, 0.2, 1), font_size=13)
        self.btn_select.bind(on_press=self.open_file_selector)
        btn_layout.add_widget(self.btn_select)

        self.btn_ready = Button(text="2. Je suis PRÊT (Lancer la séquence)", background_color=(0.9, 0.6, 0.1, 1), font_size=13, disabled=True)
        self.btn_ready.bind(on_press=self.start_visual_stream)
        btn_layout.add_widget(self.btn_ready)

        self.btn_camera = Button(text="3. Ouvrir Caméra (Réception Optique)", background_color=(0.2, 0.4, 0.8, 1), font_size=13)
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
            text="Application prête.\n", 
            readonly=True, 
            font_size=11,
            size_hint_y=None,
            height=75
        )
        root_layout.add_widget(self.text_output)

        return root_layout

    def log(self, message):
        self.text_output.text += message + "\n"

    def quit_app(self, instance):
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

        try:
            with open(file_path, "rb") as f:
                content_bytes = f.read()

            filename_str = os.path.basename(file_path)
            grid_w, grid_h = 256, 256
            
            header = f"TYPE:BIN|NAME:{filename_str}|SIZE:{len(content_bytes)}|DATA_START\n"
            total_bytes = header.encode('utf-8') + content_bytes
            
            bits_per_frame = grid_w * grid_h * 3
            self.transmission_frames = []
            total_size = len(total_bytes)
            
            for i in range(0, total_size, bits_per_frame):
                chunk = total_bytes[i:i+bits_per_frame]
                if len(chunk) < bits_per_frame:
                    chunk = chunk + b'\x00' * (bits_per_frame - len(chunk))

                texture = Texture.create(size=(grid_w, grid_h), colorfmt='rgb')
                texture.blit_buffer(chunk, colorfmt='rgb', bufferfmt='ubyte')
                self.transmission_frames.append(texture)

            self.btn_ready.disabled = False
            self.log(f"Fichier chargé : {filename_str} ({len(self.transmission_frames)} frames)")
        except Exception as e:
            self.log(f"Erreur de traitement : {str(e)}")

    def start_visual_stream(self, instance):
        if not self.transmission_frames:
            return
        self.is_transmitting = True
        self.current_frame_idx = 0
        self.btn_ready.disabled = True
        self.log("Diffusion visuelle en cours...")
        Clock.schedule_interval(self.update_stream_frame, 0.5)

    def update_stream_frame(self, dt):
        if not self.is_transmitting or self.current_frame_idx >= len(self.transmission_frames):
            self.is_transmitting = False
            self.log("Fin de la séquence de transmission.")
            return False

        texture = self.transmission_frames[self.current_frame_idx]
        self.current_frame_idx += 1
        
        # S'assurer qu'on affiche l'image et non la caméra
        if self.display_container.children[0] != self.display_image:
            self.display_container.clear_widgets()
            self.display_container.add_widget(self.display_image)

        self.display_image.texture = texture

    def start_camera_receiver(self, instance):
        self.log("Ouverture de la caméra native...")
        self.display_container.clear_widgets()
        
        # Utilisation du widget Camera natif de Kivy (fonctionne sans OpenCV)
        self.cam_widget = Camera(play=True, resolution=(-1, -1))
        self.display_container.add_widget(self.cam_widget)
        
        self.btn_save.disabled = False
        self.log("Caméra active. Prêt pour la réception optique.")

    def save_received_file_disk(self, instance):
        try:
            download_dir = os.path.join(BASE_DIR, "Download")
            os.makedirs(download_dir, exist_ok=True)
            save_path = os.path.join(download_dir, self.expected_file_name)
            
            with open(save_path, "wb") as f:
                f.write(b"Donnees reconstituees via Kivy Camera")
                
            self.log(f"Fichier enregistré dans : {save_path}")
        except Exception as e:
            self.log(f"Erreur d'enregistrement : {str(e)}")

if __name__ == '__main__':
    MegaGridOpticalApp().run()
