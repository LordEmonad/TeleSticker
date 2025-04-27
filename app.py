import os
import time
import uuid
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from PIL import Image, ImageTk
from pathlib import Path

# Constants for Telegram sticker requirements
MAX_IMAGE_SIZE = 512
MAX_VIDEO_DURATION = 3  # seconds
MAX_VIDEO_SIZE_KB = 256  # KB
ICON_SIZE = 100  # pixels
MAX_ICON_SIZE_KB = 32  # KB
VIDEO_FPS = 30
OUTPUT_DIR = "output"

# Ensure the output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def clean_temp_files():
    """Clean temporary processed files"""
    for file in os.listdir(OUTPUT_DIR):
        file_path = os.path.join(OUTPUT_DIR, file)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error removing file {file_path}: {e}")

def resize_image(input_path, output_path, output_format='webp', is_icon=False):
    """Resize image to fit Telegram sticker requirements or icon requirements"""
    try:
        # Open the image
        img = Image.open(input_path)
        
        if is_icon:
            # For icons, use fixed 100x100 size
            new_width = new_height = ICON_SIZE
        else:
            # Calculate new dimensions
            width, height = img.size
            ratio = MAX_IMAGE_SIZE / max(width, height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
        
        # Resize the image
        img = img.resize((new_width, new_height), Image.LANCZOS)
        
        # Save in the appropriate format
        if output_format == 'webp':
            img.save(output_path, 'WEBP', quality=95)
        else:  # png
            img.save(output_path, 'PNG')
            
        return True
    except Exception as e:
        print(f"Error resizing image: {e}")
        return False

def convert_video(input_path, output_path, is_icon=False):
    """Convert video to WEBM with VP9 codec for Telegram stickers or sticker icons"""
    try:
        # Ensure output path is .webm
        if not output_path.endswith('.webm'):
            output_path = output_path.rsplit('.', 1)[0] + '.webm'
        
        # Calculate dimensions based on whether this is a regular sticker or an icon
        target_size = ICON_SIZE if is_icon else MAX_IMAGE_SIZE
        max_size_kb = MAX_ICON_SIZE_KB if is_icon else MAX_VIDEO_SIZE_KB
        
        # Get video dimensions using FFprobe
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0", input_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse dimensions or use defaults
        try:
            dimensions = result.stdout.strip().split(",")
            width = int(dimensions[0])
            height = int(dimensions[1])
        except (ValueError, IndexError):
            width, height = 1280, 720
        
        # For icons, use fixed 100x100 size
        if is_icon:
            new_width = new_height = ICON_SIZE
        else:
            # Calculate new dimensions to fit target size max
            ratio = target_size / max(width, height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            
            # Ensure even dimensions for video codecs
            new_width = new_width if new_width % 2 == 0 else new_width + 1
            new_height = new_height if new_height % 2 == 0 else new_height + 1
        
        # Try different bitrates until we get file size below limit
        # Start with lower bitrate for icons
        bitrate = 150 if is_icon else 300
        success = False
        
        for attempt in range(5):  # Try up to 5 different bitrates
            # Add loop filter for icons to ensure looping
            loop_filter = ",loop=0:32767:0" if is_icon else ""
            
            # Direct FFmpeg command with VP9 codec
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-t", str(MAX_VIDEO_DURATION),  # Max 3 seconds
                "-vf", f"scale={new_width}:{new_height},fps={VIDEO_FPS}{loop_filter}",
                "-c:v", "libvpx-vp9",
                "-pix_fmt", "yuva420p",  # Format with alpha channel
                "-an",  # No audio
                "-b:v", f"{bitrate}k",
                "-crf", "30",
                "-deadline", "good",
                "-auto-alt-ref", "0",
                output_path
            ]
            
            # Run the command
            subprocess.run(cmd, capture_output=True, check=True)
            
            # Check if file is within size limit
            file_size_kb = os.path.getsize(output_path) / 1024
            
            if file_size_kb <= max_size_kb:
                success = True
                break
            
            # Reduce bitrate for next attempt
            bitrate = int(bitrate * 0.6)  # Reduce by 40%
            print(f"File too large: {file_size_kb:.1f} KB. Trying with bitrate {bitrate}k")
        
        return os.path.exists(output_path) and file_size_kb <= max_size_kb
    
    except Exception as e:
        print(f"Error converting video: {e}")
        return False

class TelegramStickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TeleSticker")
        self.root.geometry("800x600")
        self.root.minsize(800, 600)
        
        # Set style
        self.style = ttk.Style()
        self.style.configure("TButton", font=("Arial", 10))
        self.style.configure("TLabel", font=("Arial", 10))
        
        # Variables
        self.image_files = []
        self.video_files = []
        self.icon_video_file = None
        self.icon_image_file = None
        self.output_format = tk.StringVar(value="webp")
        self.create_video_icon = tk.BooleanVar(value=False)
        self.create_image_icon = tk.BooleanVar(value=False)
        
        # Create UI
        self.create_ui()
        
    def create_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Telegram Sticker Processor", font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # Description
        desc_text = (
            "Convert images and videos to Telegram sticker format:\n"
            "• Images: Resized to 512px max on one side, PNG/WEBP format\n"
            "• Videos: Converted to WEBM with VP9 codec (max 512px, 3s, 256KB)"
        )
        desc_label = ttk.Label(main_frame, text=desc_text, justify="left")
        desc_label.pack(pady=5, anchor="w")
        
        # File selection frame
        file_frame = ttk.LabelFrame(main_frame, text="Upload Files", padding=10)
        file_frame.pack(fill="x", pady=10)
        
        # Images selection
        img_frame = ttk.Frame(file_frame)
        img_frame.pack(fill="x", pady=5)
        
        img_btn = ttk.Button(img_frame, text="Select Images", command=self.select_images)
        img_btn.pack(side="left", padx=5)
        
        self.img_label = ttk.Label(img_frame, text="No images selected")
        self.img_label.pack(side="left", padx=5, fill="x", expand=True)
        
        # Videos selection
        vid_frame = ttk.Frame(file_frame)
        vid_frame.pack(fill="x", pady=5)
        
        vid_btn = ttk.Button(vid_frame, text="Select Videos", command=self.select_videos)
        vid_btn.pack(side="left", padx=5)
        
        self.vid_label = ttk.Label(vid_frame, text="No videos selected")
        self.vid_label.pack(side="left", padx=5, fill="x", expand=True)
        
        # Options frame
        option_frame = ttk.LabelFrame(main_frame, text="Options", padding=10)
        option_frame.pack(fill="x", pady=10)
        
        # Image format selection
        format_frame = ttk.Frame(option_frame)
        format_frame.pack(fill="x", pady=5)
        
        format_label = ttk.Label(format_frame, text="Image Output Format:")
        format_label.pack(side="left", padx=5)
        
        webp_radio = ttk.Radiobutton(format_frame, text="WEBP (smaller)", variable=self.output_format, value="webp")
        webp_radio.pack(side="left", padx=10)
        
        png_radio = ttk.Radiobutton(format_frame, text="PNG", variable=self.output_format, value="png")
        png_radio.pack(side="left", padx=10)
        
        # Sticker set icon options frame
        icons_label_frame = ttk.LabelFrame(option_frame, text="Sticker Set Icon (100x100px)", padding=5)
        icons_label_frame.pack(fill="x", pady=5)
        
        # Video icon option
        video_icon_frame = ttk.Frame(icons_label_frame)
        video_icon_frame.pack(fill="x", pady=2)
        
        video_icon_check = ttk.Checkbutton(video_icon_frame, 
                                         text="Create video icon (WEBM, 32KB max)", 
                                         variable=self.create_video_icon)
        video_icon_check.pack(side="left", padx=5)
        
        video_icon_btn = ttk.Button(video_icon_frame, text="Select Video", command=self.select_icon_video)
        video_icon_btn.pack(side="left", padx=10)
        
        self.video_icon_label = ttk.Label(video_icon_frame, text="No video selected")
        self.video_icon_label.pack(side="left", padx=5, fill="x", expand=True)
        
        # Static image icon option
        image_icon_frame = ttk.Frame(icons_label_frame)
        image_icon_frame.pack(fill="x", pady=2)
        
        image_icon_check = ttk.Checkbutton(image_icon_frame, 
                                         text="Create static image icon (PNG/WEBP)", 
                                         variable=self.create_image_icon)
        image_icon_check.pack(side="left", padx=5)
        
        image_icon_btn = ttk.Button(image_icon_frame, text="Select Image", command=self.select_icon_image)
        image_icon_btn.pack(side="left", padx=10)
        
        self.image_icon_label = ttk.Label(image_icon_frame, text="No image selected")
        self.image_icon_label.pack(side="left", padx=5, fill="x", expand=True)
        
        # Process button
        process_btn = ttk.Button(main_frame, text="Process Files", command=self.process_files)
        process_btn.pack(pady=10)
        
        # Status output
        status_frame = ttk.LabelFrame(main_frame, text="Processing Status", padding=10)
        status_frame.pack(fill="both", expand=True, pady=10)
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=10, wrap=tk.WORD)
        self.status_text.pack(fill="both", expand=True)
        self.status_text.config(state="disabled")
        
        # Results frame
        result_frame = ttk.Frame(main_frame, padding=10)
        result_frame.pack(fill="x", pady=5)
        
        self.result_label = ttk.Label(result_frame, text="")
        self.result_label.pack(side="left", fill="x", expand=True)
        
        self.open_output_btn = ttk.Button(result_frame, text="Open Output Folder", command=self.open_output_folder)
        self.open_output_btn.pack(side="right", padx=5)
        self.open_output_btn.config(state="disabled")
        
    def select_images(self):
        files = filedialog.askopenfilenames(
            title="Select Images",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.webp *.bmp *.tiff")
            ]
        )
        
        if files:
            self.image_files = files
            self.img_label.config(text=f"{len(files)} image(s) selected")
    
    def select_videos(self):
        files = filedialog.askopenfilenames(
            title="Select Videos",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.avi *.wmv *.webm *.mkv")
            ]
        )
        
        if files:
            self.video_files = files
            self.vid_label.config(text=f"{len(files)} video(s) selected")
            
    def select_icon_video(self):
        file = filedialog.askopenfilename(
            title="Select Icon Video",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.avi *.wmv *.webm *.mkv")
            ]
        )
        
        if file:
            self.icon_video_file = file
            self.video_icon_label.config(text=f"Selected: {os.path.basename(file)}")
            self.create_video_icon.set(True)  # Auto-enable icon creation when file is selected
    
    def select_icon_image(self):
        file = filedialog.askopenfilename(
            title="Select Icon Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.webp *.bmp *.tiff")
            ]
        )
        
        if file:
            self.icon_image_file = file
            self.image_icon_label.config(text=f"Selected: {os.path.basename(file)}")
            self.create_image_icon.set(True)  # Auto-enable icon creation when file is selected
    
    def update_status(self, text, append=True):
        self.status_text.config(state="normal")
        if not append:
            self.status_text.delete(1.0, tk.END)
        self.status_text.insert(tk.END, text)
        self.status_text.see(tk.END)
        self.status_text.config(state="disabled")
        self.root.update()
    
    def processing_thread(self):
        # Clean temporary files
        clean_temp_files()
        
        processed_files = []
        self.update_status("", append=False)
        
        # Process images
        if self.image_files:
            self.update_status(f"Processing {len(self.image_files)} images...\n")
            for i, img_path in enumerate(self.image_files):
                try:
                    filename = os.path.basename(img_path)
                    output_filename = f"sticker_{i+1}_{int(time.time())}.{self.output_format.get()}"
                    output_path = os.path.join(OUTPUT_DIR, output_filename)
                    
                    self.update_status(f"• Processing image: {filename}... ")
                    self.root.update()  # Force UI update to show progress
                    
                    success = resize_image(img_path, output_path, self.output_format.get())
                    
                    if success:
                        processed_files.append(output_path)
                        self.update_status("✓\n")
                    else:
                        self.update_status("❌ Failed\n")
                except Exception as e:
                    self.update_status(f"❌ Error: {str(e)}\n")
        
        # Process videos
        if self.video_files:
            self.update_status(f"\nProcessing {len(self.video_files)} videos...\n")
            for i, video_path in enumerate(self.video_files):
                try:
                    filename = os.path.basename(video_path)
                    output_filename = f"sticker_{i+1}_{int(time.time())}.webm"
                    output_path = os.path.join(OUTPUT_DIR, output_filename)
                    
                    self.update_status(f"• Processing video: {filename}... ")
                    self.root.update()  # Force UI update to show progress
                    
                    # Convert video to WEBM format for Telegram stickers
                    success = convert_video(video_path, output_path)
                    
                    if success:
                        processed_files.append(output_path)
                        self.update_status("✓\n")
                    else:
                        self.update_status("❌ Failed\n")
                except Exception as e:
                    self.update_status(f"❌ Error: {str(e)}\n")
                    
                # Force UI update after each video to show progress
                self.root.update()
        
        # Process video sticker set icon if enabled
        if self.create_video_icon.get() and self.icon_video_file:
            self.update_status(f"\nProcessing video sticker set icon...\n")
            try:
                filename = os.path.basename(self.icon_video_file)
                output_filename = f"icon_video_{int(time.time())}.webm"
                output_path = os.path.join(OUTPUT_DIR, output_filename)
                
                self.update_status(f"• Processing icon video: {filename}... ")
                self.root.update()  # Force UI update to show progress
                
                # Convert video to icon format (100x100, 32KB max)
                success = convert_video(self.icon_video_file, output_path, is_icon=True)
                
                if success:
                    processed_files.append(output_path)
                    self.update_status("✓\n")
                    self.update_status("  (Icon must be set separately in @Stickers bot)\n")
                else:
                    self.update_status("❌ Failed - Could not meet size requirements\n")
            except Exception as e:
                self.update_status(f"❌ Error: {str(e)}\n")
        
        # Process static image sticker set icon if enabled
        if self.create_image_icon.get() and self.icon_image_file:
            self.update_status(f"\nProcessing static image sticker set icon...\n")
            try:
                filename = os.path.basename(self.icon_image_file)
                # Use the same format as selected for stickers or default to webp
                icon_format = self.output_format.get()
                output_filename = f"icon_static_{int(time.time())}.{icon_format}"
                output_path = os.path.join(OUTPUT_DIR, output_filename)
                
                self.update_status(f"• Processing icon image: {filename}... ")
                self.root.update()  # Force UI update to show progress
                
                # Resize image to icon format (100x100)
                success = resize_image(self.icon_image_file, output_path, icon_format, is_icon=True)
                
                if success:
                    processed_files.append(output_path)
                    self.update_status("✓\n")
                    self.update_status("  (Icon must be set separately in @Stickers bot)\n")
                else:
                    self.update_status("❌ Failed\n")
            except Exception as e:
                self.update_status(f"❌ Error: {str(e)}\n")
        
        # Complete processing
        if processed_files:
            self.update_status(f"\nProcessing complete!\n")
            self.update_status(f"Files saved to: {os.path.abspath(OUTPUT_DIR)}\n")
            
            # Update UI from main thread
            self.root.after(0, lambda: self.result_label.config(
                text=f"Processed {len(processed_files)} file(s) to output folder"))
            self.root.after(0, lambda: self.open_output_btn.config(state="normal"))
        else:
            self.update_status("\nNo files were successfully processed.\n")
    
    def process_files(self):
        has_icon = (self.create_video_icon.get() and self.icon_video_file) or (self.create_image_icon.get() and self.icon_image_file)
        if not self.image_files and not self.video_files and not has_icon:
            messagebox.showwarning("No Files", "Please select at least one image, video file, or icon.")
            return
        
        # Reset result section
        self.result_label.config(text="")
        self.open_output_btn.config(state="disabled")
        
        # Start processing in a separate thread
        threading.Thread(target=self.processing_thread, daemon=True).start()
    
    def open_output_folder(self):
        # Open file explorer to the output directory
        folder_path = os.path.abspath(OUTPUT_DIR)
        if os.path.exists(folder_path):
            try:
                os.startfile(folder_path)
            except AttributeError:  # if not on Windows
                subprocess.call(["open", folder_path])

# Main application entry point
if __name__ == "__main__":
    root = tk.Tk()
    app = TelegramStickerApp(root)
    root.mainloop()
