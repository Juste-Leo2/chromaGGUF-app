# -*- coding: utf-8 -*-
# src/main.py
import os
import sys
import threading
import time
import random
import gc
import psutil
from PIL import Image

# --- Étape 1: Configuration de l'environnement ComfyUI ---
script_dir = os.path.dirname(os.path.abspath(__file__))
comfyui_dir = os.path.join(script_dir, "ComfyUI")
sys.path.insert(0, comfyui_dir)
custom_nodes_dir = os.path.join(script_dir, "custom_nodes")
sys.path.insert(0, custom_nodes_dir)
from ComfyUIGGUF import nodes as gguf_nodes_module
NODE_CLASS_MAPPINGS = gguf_nodes_module.NODE_CLASS_MAPPINGS
import torch
import customtkinter as ctk
from customtkinter import CTkImage, filedialog
import comfy.model_management as model_management
import comfy.utils
import folder_paths
import nodes
import comfy.sample
import latent_preview

nodes.NODE_CLASS_MAPPINGS.update(NODE_CLASS_MAPPINGS)


# --- Logique de KSampler personnalisée (INCHANGÉE) ---
def ksampler_with_custom_callback(model, seed, steps, cfg, sampler_name, scheduler, positive, negative, latent, denoise=1.0, disable_noise=False, start_step=None, last_step=None, force_full_denoise=False, custom_callback=None):
    latent_image = latent["samples"]
    latent_image = comfy.sample.fix_empty_latent_channels(model, latent_image)
    if disable_noise: noise = torch.zeros_like(latent_image)
    else: noise = comfy.sample.prepare_noise(latent_image, seed, None)
    
    samples = comfy.sample.sample(model, noise, steps, cfg, sampler_name, scheduler, positive, negative, latent_image,
                                  denoise=denoise, disable_noise=disable_noise, start_step=start_step, last_step=last_step,
                                  force_full_denoise=force_full_denoise, noise_mask=latent.get("noise_mask"), 
                                  callback=custom_callback, disable_pbar=True, seed=seed)
    out = latent.copy()
    out["samples"] = samples
    return (out, )

class KSamplerWithProgress:
    @classmethod
    def INPUT_TYPES(s): return nodes.KSampler.INPUT_TYPES()
    RETURN_TYPES = ("LATENT",)
    FUNCTION = "sample"
    CATEGORY = "sampling"
    def sample(self, model, seed, steps, cfg, sampler_name, scheduler, positive, negative, latent_image, denoise=1.0, callback=None):
        return ksampler_with_custom_callback(model, seed, steps, cfg, sampler_name, scheduler, positive, negative, latent_image, denoise=denoise, custom_callback=callback)

NODE_CLASS_MAPPINGS['KSamplerWithProgress'] = KSamplerWithProgress


# --- Étape 2: Classe Backend pour la Génération d'Image ---
class ImageGenerator:
    def __init__(self, update_status_callback=None):
        self.update_status_callback = update_status_callback
        self.is_setup = False 
        self.unet, self.clip, self.vae = None, None, None
        self.clip_text_encoder, self.empty_latent_image, self.sampler, self.vae_decoder = None, None, None, None
        self.models_base_path = os.path.abspath(os.path.join(script_dir, '..', 'models'))
        folder_paths.add_model_folder_path("unet_gguf", self.models_base_path)
        folder_paths.add_model_folder_path("clip_gguf", self.models_base_path)
        folder_paths.add_model_folder_path("vae", self.models_base_path)
        self.unet_path = os.path.join("chroma-unlocked-v37", "chroma-unlocked-v37-Q4_0.gguf")
        self.clip_path = "t5-v1_1-xxl-encoder-Q4_K_M.gguf"
        self.vae_path = "ae.safetensors"
        self.output_dir = os.path.join(comfyui_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)
        
    def _update_status(self, message):
        if self.update_status_callback: self.update_status_callback(message, "white")

    def setup_persistent_environment(self):
        self._update_status("Chargement des modèles en RAM...")
        self.unet = NODE_CLASS_MAPPINGS['UnetLoaderGGUF']().load_unet(self.unet_path)[0]
        self.clip = NODE_CLASS_MAPPINGS['CLIPLoaderGGUF']().load_clip(self.clip_path, type="chroma")[0]
        self.vae = nodes.NODE_CLASS_MAPPINGS['VAELoader']().load_vae(self.vae_path)[0]
        self._update_status("Préparation des nœuds de workflow...")
        self.clip_text_encoder = nodes.NODE_CLASS_MAPPINGS['CLIPTextEncode']()
        self.empty_latent_image = nodes.NODE_CLASS_MAPPINGS['EmptyLatentImage']()
        self.sampler = KSamplerWithProgress()
        self.vae_decoder = nodes.NODE_CLASS_MAPPINGS['VAEDecode']()
        self.is_setup = True
        self._update_status("Environnement prêt.")
        
    def unload_all_models(self):
        self._update_status("Déchargement des modèles...")
        self.unet, self.clip, self.vae = None, None, None
        self.clip_text_encoder, self.empty_latent_image, self.sampler, self.vae_decoder = None, None, None, None
        self.is_setup = False
        gc.collect()
        comfy.model_management.unload_all_models()
        self._update_status("Modèles déchargés de la RAM et la VRAM.")

    def generate(self, **kwargs):
        mode = kwargs.get("management_mode")
        if mode == "Performant":
            return self._generate_performant(**kwargs)
        elif mode == "Économique":
            return self._generate_economique(**kwargs)

    def _generate_performant(self, positive_prompt, negative_prompt, steps, cfg, width, height, progress_callback, **kwargs):
        if not self.is_setup: self.setup_persistent_environment()
        try:
            self._update_status("Mode Performant: génération...")
            (positive_conditioning,) = self.clip_text_encoder.encode(clip=self.clip, text=positive_prompt)
            (negative_conditioning,) = self.clip_text_encoder.encode(clip=self.clip, text=negative_prompt)
            (latent,) = self.empty_latent_image.generate(width=width, height=height, batch_size=1)
            (sampled_latent,) = self.sampler.sample(model=self.unet, seed=random.randint(0, 2**32-1), steps=steps, cfg=cfg, sampler_name="euler", scheduler="beta", positive=positive_conditioning, negative=negative_conditioning, latent_image=latent, denoise=1.0, callback=progress_callback)
            (decoded_image,) = self.vae_decoder.decode(samples=sampled_latent, vae=self.vae)
            return self._save_result_image(decoded_image)
        finally:
            self._update_status("Fin de la génération (modèles en RAM).")

    def _generate_economique(self, positive_prompt, negative_prompt, steps, cfg, width, height, progress_callback, **kwargs):
        self._update_status("Mode Économique: workflow sans état...")
        decoded_image = None
        try:
            self._update_status("Éco: Chargement/utilisation de CLIP...")
            clip_model = NODE_CLASS_MAPPINGS['CLIPLoaderGGUF']().load_clip(self.clip_path, type="chroma")[0]
            clip_encoder = nodes.NODE_CLASS_MAPPINGS['CLIPTextEncode']()
            (positive_conditioning,) = clip_encoder.encode(clip=clip_model, text=positive_prompt)
            (negative_conditioning,) = clip_encoder.encode(clip=clip_model, text=negative_prompt)
        finally:
            self._update_status("Éco: Déchargement de CLIP..."); del clip_model, clip_encoder; gc.collect(); comfy.model_management.unload_all_models()
        try:
            self._update_status("Éco: Chargement/utilisation de l'UNet...")
            unet_model = NODE_CLASS_MAPPINGS['UnetLoaderGGUF']().load_unet(self.unet_path)[0]
            sampler = KSamplerWithProgress()
            latent_image_node = nodes.NODE_CLASS_MAPPINGS['EmptyLatentImage']()
            (latent,) = latent_image_node.generate(width=width, height=height, batch_size=1)
            (sampled_latent,) = sampler.sample(model=unet_model, seed=random.randint(0, 2**32-1), steps=steps, cfg=cfg, sampler_name="euler", scheduler="beta", positive=positive_conditioning, negative=negative_conditioning, latent_image=latent, denoise=1.0, callback=progress_callback)
        finally:
            self._update_status("Éco: Déchargement de l'UNet..."); del unet_model, sampler, latent_image_node; gc.collect(); comfy.model_management.unload_all_models()
        try:
            self._update_status("Éco: Chargement/utilisation du VAE...")
            vae_model = nodes.NODE_CLASS_MAPPINGS['VAELoader']().load_vae(self.vae_path)[0]
            vae_decoder = nodes.NODE_CLASS_MAPPINGS['VAEDecode']()
            # ## CORRECTION ##: Utilisation de la variable locale 'vae_model' et non 'self.vae'
            (decoded_image,) = vae_decoder.decode(samples=sampled_latent, vae=vae_model)
        finally:
            self._update_status("Éco: Déchargement du VAE..."); del vae_model, vae_decoder; gc.collect(); comfy.model_management.unload_all_models()
        if decoded_image is not None: return self._save_result_image(decoded_image)
        return None

    def _save_result_image(self, decoded_image):
        image_to_save = decoded_image.detach()
        result = nodes.NODE_CLASS_MAPPINGS['SaveImage']().save_images(images=image_to_save, filename_prefix=f"output_{time.strftime('%Y%m%d-%H%M%S')}")
        return os.path.join(self.output_dir, result['ui']['images'][0]['filename'])

# --- Étape 3: Classe Frontend avec CustomTkinter ---
class App(ctk.CTk):
    def __init__(self, generator: ImageGenerator):
        super().__init__()
        self.generator = generator
        self.last_pil_image = None
        self.vram_gb = 0
        self.ram_gb = 0
        self.title("Générateur d'Image GGUF")
        self.geometry("1300x850")
        ctk.set_appearance_mode("dark")
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        self.controls_frame = ctk.CTkFrame(self, width=350, corner_radius=0)
        self.controls_frame.grid(row=0, column=0, rowspan=4, sticky="nsw")
        self.controls_frame.grid_rowconfigure(7, weight=1)
        self.logo_label = ctk.CTkLabel(self.controls_frame, text="Paramètres", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 10))
        self.positive_prompt_label = ctk.CTkLabel(self.controls_frame, text="Prompt Positif:")
        self.positive_prompt_label.grid(row=1, column=0, columnspan=2, padx=20, pady=(10, 0), sticky="w")
        self.positive_prompt_entry = ctk.CTkTextbox(self.controls_frame, height=100)
        self.positive_prompt_entry.grid(row=2, column=0, columnspan=2, padx=20, pady=5, sticky="ew")
        self.positive_prompt_entry.insert("0.0", "a beautiful photo of nature, 8k, photorealistic")
        self.negative_prompt_label = ctk.CTkLabel(self.controls_frame, text="Prompt Négatif:")
        self.negative_prompt_label.grid(row=3, column=0, columnspan=2, padx=20, pady=(10, 0), sticky="w")
        self.negative_prompt_entry = ctk.CTkTextbox(self.controls_frame, height=80)
        self.negative_prompt_entry.grid(row=4, column=0, columnspan=2, padx=20, pady=5, sticky="ew")
        self.negative_prompt_entry.insert("0.0", "ugly, bad quality, watermark, text")
        self.sliders_frame = ctk.CTkFrame(self.controls_frame)
        self.sliders_frame.grid(row=5, column=0, columnspan=2, padx=20, pady=10, sticky="ew")
        self.sliders_frame.grid_columnconfigure(1, weight=1)
        self.steps_label = ctk.CTkLabel(self.sliders_frame, text="Steps:")
        self.steps_label.grid(row=0, column=0, padx=(10,5), pady=10, sticky="w")
        self.steps_value_label = ctk.CTkLabel(self.sliders_frame, text="26")
        self.steps_value_label.grid(row=0, column=2, padx=(5,10), pady=10, sticky="e")
        self.steps_slider = ctk.CTkSlider(self.sliders_frame, from_=10, to=100, number_of_steps=90, command=lambda v: self.steps_value_label.configure(text=f"{int(v)}"))
        self.steps_slider.set(26)
        self.steps_slider.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        self.cfg_label = ctk.CTkLabel(self.sliders_frame, text="CFG:")
        self.cfg_label.grid(row=1, column=0, padx=(10,5), pady=10, sticky="w")
        self.cfg_value_label = ctk.CTkLabel(self.sliders_frame, text="4.0")
        self.cfg_value_label.grid(row=1, column=2, padx=(5,10), pady=10, sticky="e")
        self.cfg_slider = ctk.CTkSlider(self.sliders_frame, from_=1, to=15, number_of_steps=140, command=lambda v: self.cfg_value_label.configure(text=f"{v:.1f}"))
        self.cfg_slider.set(4.0)
        self.cfg_slider.grid(row=1, column=1, padx=5, pady=10, sticky="ew")
        self.size_label = ctk.CTkLabel(self.sliders_frame, text="Taille (W x H):")
        self.size_label.grid(row=2, column=0, columnspan=3, padx=10, pady=(10,0), sticky="w")
        self.size_value_label = ctk.CTkLabel(self.sliders_frame, text="512 x 512")
        self.size_value_label.grid(row=2, column=1, columnspan=2, padx=10, pady=(10,0), sticky="e")
        self.width_slider = ctk.CTkSlider(self.sliders_frame, from_=256, to=1024, number_of_steps=12, command=self._update_size_label)
        self.width_slider.set(512)
        self.width_slider.grid(row=3, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
        self.height_slider = ctk.CTkSlider(self.sliders_frame, from_=256, to=1024, number_of_steps=12, command=self._update_size_label)
        self.height_slider.set(512)
        self.height_slider.grid(row=4, column=0, columnspan=3, padx=10, pady=5, sticky="ew")

        self.resource_frame = ctk.CTkFrame(self.controls_frame)
        self.resource_frame.grid(row=6, column=0, columnspan=2, padx=20, pady=(10,0), sticky="ew")
        self.resource_label = ctk.CTkLabel(self.resource_frame, text="Gestion Mémoire :")
        self.resource_label.pack(padx=10, pady=(10,5), side="top", anchor="w")
        
        self.management_mode_var = ctk.StringVar()
        self.management_mode_selector = ctk.CTkSegmentedButton(
            self.resource_frame, 
            values=["Performant", "Économique"],
            variable=self.management_mode_var,
            command=self.on_mode_change
        )
        self.management_mode_selector.pack(padx=10, pady=(5,5), expand=True, fill="x")

        self.recommendation_label = ctk.CTkLabel(self.resource_frame, text="", text_color="gray", font=ctk.CTkFont(size=12))
        self.recommendation_label.pack(padx=10, pady=(0, 10), side="top", anchor="w")
        
        # ## CORRECTION ##: Suppression du bouton décharger
        self.generate_button = ctk.CTkButton(self.controls_frame, text="Générer", command=self.start_generation_thread)
        self.generate_button.grid(row=8, column=0, columnspan=2, padx=20, pady=20, sticky="ew")

        self.status_label = ctk.CTkLabel(self.controls_frame, text="Prêt. Cliquez sur 'Générer'.")
        self.status_label.grid(row=9, column=0, columnspan=2, padx=20, pady=10)
        
        self.progress_bar = ctk.CTkProgressBar(self.controls_frame, mode="determinate")
        self.progress_bar.set(0)
        self.progress_bar.grid(row=10, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="ew")

        self.image_frame = ctk.CTkFrame(self)
        self.image_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.image_frame.grid_rowconfigure(0, weight=1); self.image_frame.grid_columnconfigure(0, weight=1)
        self.image_label = ctk.CTkLabel(self.image_frame, text="L'image générée apparaîtra ici", height=512)
        self.image_label.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.save_button = ctk.CTkButton(self.image_frame, text="Sauvegarder l'image", command=self._save_image, state="disabled")
        self.save_button.grid(row=1, column=0, padx=10, pady=10)
        
        self._detect_hardware_and_set_recommendation()

    def _detect_hardware_and_set_recommendation(self):
        self.ram_gb = psutil.virtual_memory().total / (1024**3)
        try:
            if torch.cuda.is_available():
                vram_bytes = torch.cuda.get_device_properties(0).total_memory
                self.vram_gb = vram_bytes / (1024**3)
                self.resource_label.configure(text=f"Mémoire ({self.ram_gb:.1f}Go RAM, {self.vram_gb:.1f}Go VRAM):")
                if self.vram_gb >= 8 and self.ram_gb > 32:
                    default_mode = "Performant"
                    reco_text = "Recommandé: Performant (Vitesse max)"
                else:
                    default_mode = "Économique"
                    reco_text = "Recommandé: Économique (Faible RAM/VRAM)"
                self.management_mode_var.set(default_mode)
                self.recommendation_label.configure(text=reco_text)
            else:
                self.resource_label.configure(text=f"Mémoire ({self.ram_gb:.1f}Go RAM, Pas de GPU):")
                self.management_mode_var.set("Économique"); self.recommendation_label.configure(text="Mode Économique utilisé (pas de GPU).")
                self.management_mode_selector.configure(state="disabled")
        except Exception as e:
            self.recommendation_label.configure(text="Erreur détection hardware.", text_color="orange"); self.management_mode_var.set("Économique")

    def on_mode_change(self, new_mode):
        print(f"Changement de mode vers: {new_mode}")
        if new_mode == "Économique" and self.generator.is_setup:
            print("Passage de Performant à Économique: déchargement des modèles.")
            self._trigger_unload_in_background()

    def _trigger_unload_in_background(self):
        self.generate_button.configure(state="disabled")
        thread = threading.Thread(target=self.generator.unload_all_models)
        thread.start()
        self.after(100, self._wait_for_unload, thread)
        
    def _wait_for_unload(self, thread):
        if thread.is_alive(): self.after(100, self._wait_for_unload, thread)
        else: self.generate_button.configure(state="normal")

    def _update_size_label(self, _=None): w = int(self.width_slider.get() / 64) * 64; h = int(self.height_slider.get() / 64) * 64; self.size_value_label.configure(text=f"{w} x {h}")
    def _save_image(self):
        if not self.last_pil_image: return
        filepath = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")])
        if filepath:
            try: self.last_pil_image.save(filepath); self.update_status(f"Image sauvegardée: {os.path.basename(filepath)}")
            except Exception as e: self.update_status(f"Erreur de sauvegarde: {e}", "red")

    def start_generation_thread(self):
        self.generate_button.configure(state="disabled"); self.save_button.configure(state="disabled")
        self.status_label.configure(text="Initialisation...", text_color="white"); self.progress_bar.set(0)
        thread = threading.Thread(target=self.run_generation); thread.start()

    def run_generation(self):
        try:
            params = { "positive_prompt": self.positive_prompt_entry.get("1.0", "end-1c"), "negative_prompt": self.negative_prompt_entry.get("1.0", "end-1c"), "steps": int(self.steps_slider.get()), "cfg": self.cfg_slider.get(), "width": int(int(self.width_slider.get() / 64) * 64), "height": int(int(self.height_slider.get() / 64) * 64), "management_mode": self.management_mode_var.get(), "progress_callback": self.update_progress_from_thread }
            image_path = self.generator.generate(**params)
            if image_path: self.after(0, self.update_ui_with_image, image_path)
        except Exception as e:
            print(f"Erreur lors de la génération: {e}"); import traceback; traceback.print_exc()
            self.after(0, self.update_status, f"Erreur: {e}", "red")
        finally:
            self.after(0, self.generation_finished)

    def update_status_from_thread(self, message, color="white"): self.after(0, self.update_status, message, color)
    def update_progress_from_thread(self, step, denoised, x, total_steps): self.after(0, self.update_ui_progress, step, total_steps)
    def update_ui_progress(self, step, total_steps):
        progress_value = (step + 1) / total_steps; self.progress_bar.set(progress_value)
        self.status_label.configure(text=f"Diffusion: Étape {step + 1} / {total_steps}...")
    def update_status(self, text, color="white"): self.status_label.configure(text=text, text_color=color)

    def update_ui_with_image(self, image_path):
        self.update_status("Génération terminée !", "lightgreen")
        try:
            self.last_pil_image = Image.open(image_path); w, h = self.last_pil_image.size
            frame_w, frame_h = self.image_frame.winfo_width(), self.image_frame.winfo_height()
            if frame_w <= 1: frame_w = 768
            if frame_h <= 1: frame_h = 768
            ratio = min(frame_w / w, frame_h / h); new_size = (int(w * ratio), int(h * ratio))
            ctk_image = CTkImage(self.last_pil_image, size=new_size)
            self.image_label.configure(image=ctk_image, text=""); self.save_button.configure(state="normal")
        except Exception as e:
            self.update_status(f"Erreur affichage image: {e}", "red")
    
    def generation_finished(self):
        self.generate_button.configure(state="normal")

# --- Étape 4: Point d'Entrée Principal ---
if __name__ == "__main__":
    app = App(generator=None) 
    image_generator = ImageGenerator(update_status_callback=app.update_status_from_thread)
    app.generator = image_generator
    app.mainloop()