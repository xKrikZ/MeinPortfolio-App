"""
Complete icon setup for Portfolio App
Downloads and creates icons with correct sizes
"""
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io


class IconSetup:
    """Setup all required icons for the application"""
    
    def __init__(self):
        self.icons_dir = Path("assets/icons")
        self.icons_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = self.icons_dir / "temp"
        self.temp_dir.mkdir(exist_ok=True)
    
    def create_all_icons(self, button_size: int = 24):
        """
        Create all required icons
        
        Args:
            button_size: Size for button icons (16 or 24 recommended)
        """
        print("=" * 70)
        print("Portfolio App - Icon Setup")
        print("=" * 70)
        
        # Create button icons - Price Management
        print(f"\n📦 Creating PRICE MANAGEMENT icons ({button_size}x{button_size} px)...\n")
        self._create_icon("save.png", button_size, (76, 175, 80), "💾")      # Green
        self._create_icon("add.png", button_size, (76, 175, 80), "➕")       # Green
        self._create_icon("apply.png", button_size, (0, 150, 136), "✅")     # Teal
        self._create_icon("export.png", button_size, (33, 150, 243), "📊")   # Blue
        self._create_icon("filter.png", button_size, (255, 152, 0), "🔍")    # Orange
        self._create_icon("reset.png", button_size, (244, 67, 54), "↺")      # Red
        self._create_icon("refresh.png", button_size, (156, 39, 176), "🔄")  # Purple
        self._create_icon("chart.png", button_size, (33, 150, 243), "📈")    # Blue
        
        # Create button icons - Portfolio Management
        print(f"\n💼 Creating PORTFOLIO icons ({button_size}x{button_size} px)...\n")
        self._create_icon("portfolio.png", button_size, (63, 81, 181), "💼")  # Indigo
        self._create_icon("buy.png", button_size, (76, 175, 80), "🛒")        # Green
        self._create_icon("sell.png", button_size, (244, 67, 54), "💸")       # Red
        self._create_icon("transaction.png", button_size, (255, 193, 7), "💳") # Amber
        self._create_icon("profit.png", button_size, (76, 175, 80), "📈")     # Green
        self._create_icon("loss.png", button_size, (244, 67, 54), "📉")       # Red
        self._create_icon("details.png", button_size, (96, 125, 139), "📋")   # Blue Grey
        
        # Create app icon
        self._create_app_icon()
        
        print("\n" + "=" * 70)
        print("✅ All icons created successfully!")
        print(f"📁 Location: {self.icons_dir.absolute()}")
        print("=" * 70)
        
        # Cleanup
        if self.temp_dir.exists():
            import shutil
            shutil.rmtree(self.temp_dir)

    @staticmethod
    def _normalize_icon_image(
        img: Image.Image,
        target_size: int,
        padding: int = 1,
        vertical_offset: int = 0
    ) -> Image.Image:
        """Normalize icon image: trim transparent bounds, preserve ratio, center on square canvas."""
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        alpha = img.split()[3]
        bbox = alpha.getbbox()
        if bbox:
            img = img.crop(bbox)

        inner_w = max(1, target_size - (padding * 2))
        inner_h = max(1, target_size - (padding * 2))
        img.thumbnail((inner_w, inner_h), Image.Resampling.LANCZOS)

        canvas = Image.new('RGBA', (target_size, target_size), (0, 0, 0, 0))
        x_raw = (target_size - img.width) // 2
        y_raw = (target_size - img.height) // 2 + vertical_offset

        x = min(max(0, x_raw), max(0, target_size - img.width))
        y = min(max(0, y_raw), max(0, target_size - img.height))
        canvas.paste(img, (x, y), img)
        return canvas

    def _normalize_icon_file(self, file_path: Path, target_size: int) -> None:
        """Load icon file, normalize and overwrite it as clean RGBA PNG."""
        img = Image.open(file_path)
        normalized = self._normalize_icon_image(img, target_size=target_size, padding=1, vertical_offset=0)
        normalized.save(file_path, format='PNG')

    def _draw_symbol(self, draw: ImageDraw.ImageDraw, size: int, symbol_key: str) -> bool:
        """Draw crisp vector symbols for selected icons. Returns True if handled."""
        if symbol_key == "save":
            stroke = max(1, size // 14)
            left = max(4, size // 5)
            right = size - left
            top = max(4, size // 5)
            bottom = size - top

            draw.rounded_rectangle(
                [left, top, right, bottom],
                radius=max(2, size // 10),
                outline=(255, 255, 255, 255),
                width=stroke
            )

            label_h = max(3, size // 5)
            draw.rectangle(
                [left + stroke, bottom - label_h - stroke, right - stroke, bottom - stroke],
                fill=(255, 255, 255, 255)
            )

            notch_w = max(3, size // 5)
            notch_h = max(2, size // 6)
            notch_x = right - notch_w - stroke
            notch_y = top + stroke
            draw.rectangle(
                [notch_x, notch_y, notch_x + notch_w, notch_y + notch_h],
                fill=(255, 255, 255, 255)
            )
            return True

        if symbol_key == "export":
            stroke = max(1, size // 14)
            left = max(4, size // 5)
            right = size - left
            top = max(4, size // 5)
            bottom = size - top

            draw.rounded_rectangle(
                [left, top, right, bottom],
                radius=max(2, size // 10),
                outline=(255, 255, 255, 255),
                width=stroke
            )

            arrow_mid_y = top + (bottom - top) // 2
            arrow_start_x = left + max(2, size // 8)
            arrow_end_x = right - max(3, size // 7)

            draw.line(
                [(arrow_start_x, arrow_mid_y), (arrow_end_x, arrow_mid_y)],
                fill=(255, 255, 255, 255),
                width=stroke
            )

            arrow_size = max(2, size // 7)
            draw.line(
                [(arrow_end_x - arrow_size, arrow_mid_y - arrow_size), (arrow_end_x, arrow_mid_y)],
                fill=(255, 255, 255, 255),
                width=stroke
            )
            draw.line(
                [(arrow_end_x - arrow_size, arrow_mid_y + arrow_size), (arrow_end_x, arrow_mid_y)],
                fill=(255, 255, 255, 255),
                width=stroke
            )

            base_top = bottom - max(3, size // 6)
            draw.line(
                [(left + stroke, base_top), (right - stroke, base_top)],
                fill=(255, 255, 255, 255),
                width=stroke
            )
            return True

        if symbol_key == "apply":
            stroke = max(2, size // 10)
            p1 = (max(4, size // 5), size // 2)
            p2 = (size // 2 - max(1, size // 12), size - max(4, size // 4))
            p3 = (size - max(4, size // 5), max(4, size // 4))

            draw.line([p1, p2, p3], fill=(255, 255, 255, 255), width=stroke, joint="curve")
            return True

        if symbol_key == "add":
            stroke = max(2, size // 9)
            cx = size // 2
            cy = size // 2
            arm = max(4, size // 5)

            draw.line([(cx - arm, cy), (cx + arm, cy)], fill=(255, 255, 255, 255), width=stroke)
            draw.line([(cx, cy - arm), (cx, cy + arm)], fill=(255, 255, 255, 255), width=stroke)
            return True

        return False
    
    def _create_icon(self, filename: str, size: int, color: tuple, emoji: str = None):
        """Create a simple colored icon with emoji"""
        try:
            img = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Draw rounded rectangle background
            padding = 2
            radius = size // 6
            
            # Draw shape
            draw.rounded_rectangle(
                [padding, padding, size - padding, size - padding],
                radius=radius,
                fill=color + (255,),
                outline=(max(0, color[0]-40), max(0, color[1]-40), max(0, color[2]-40), 255),
                width=2
            )
            
            symbol_key = filename.replace('.png', '')

            # Draw custom vector symbols for key icons first
            custom_drawn = self._draw_symbol(draw, size, symbol_key)

            # Try to add emoji/text if available
            if (not custom_drawn) and emoji and size >= 24:
                try:
                    # Try to use a font for emoji
                    font_size = int(size * 0.5)
                    try:
                        font = ImageFont.truetype("seguiemj.ttf", font_size)  # Windows emoji font
                    except:
                        try:
                            font = ImageFont.truetype("arial.ttf", font_size)
                        except:
                            font = ImageFont.load_default()
                    
                    # Calculate text position (centered)
                    bbox = draw.textbbox((0, 0), emoji, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    x = (size - text_width) // 2
                    y = (size - text_height) // 2
                    
                    draw.text((x, y), emoji, fill='white', font=font)
                except Exception as e:
                    # If emoji rendering fails, just use the colored shape
                    pass
            
            output_path = self.icons_dir / filename
            img.save(output_path)
            self._normalize_icon_file(output_path, size)
            print(f"✅ Created: {filename} ({size}x{size})")
            
        except Exception as e:
            print(f"❌ Failed to create {filename}: {e}")
    
    def _create_app_icon(self):
        """Create multi-size .ico file for Windows"""
        print("\n🎨 Creating app icon (multi-size ICO)...\n")
        
        sizes = [16, 32, 48, 256]
        images = []
        
        for size in sizes:
            img = Image.new('RGB', (size, size), color='#1a1a2e')
            draw = ImageDraw.Draw(img)
            
            # Draw portfolio/chart visualization
            padding = size // 8
            
            # Draw folder/portfolio shape
            folder_height = size // 3
            folder_y = size // 3
            
            # Folder tab
            draw.rectangle(
                [padding, folder_y, padding + size // 3, folder_y + size // 10],
                fill='#16213e',
                outline='#0f4c75',
                width=1
            )
            
            # Folder body
            draw.rectangle(
                [padding, folder_y + size // 10, size - padding, size - padding],
                fill='#16213e',
                outline='#0f4c75',
                width=2
            )
            
            # Draw chart line inside
            if size >= 32:
                chart_padding = padding * 2
                chart_width = size - chart_padding * 2
                chart_height = (size - padding) - (folder_y + size // 10) - chart_padding
                
                # Simple upward trend line
                points = [
                    (chart_padding, size - padding - chart_padding),
                    (chart_padding + chart_width // 3, size - padding - chart_padding - chart_height // 3),
                    (chart_padding + 2 * chart_width // 3, size - padding - chart_padding - chart_height // 2),
                    (chart_padding + chart_width, size - padding - chart_padding - 2 * chart_height // 3),
                ]
                
                draw.line(points, fill='#3be373', width=max(1, size // 32), joint='curve')
            
            images.append(img)
            print(f"  ✅ Generated {size}x{size} px")
        
        # Save as ICO with multiple sizes
        ico_path = self.icons_dir / "app_icon.ico"
        images[0].save(
            ico_path,
            format='ICO',
            sizes=[(s, s) for s in sizes]
        )
        
        print(f"\n✅ Created: app_icon.ico")
        print(f"   Contains: {', '.join(f'{s}x{s}' for s in sizes)} px")
    
    def download_from_icons8(self, button_size: int = 24):
        """
        Alternative: Download from Icons8 (requires attribution)
        
        Args:
            button_size: Size for button icons
        """
        print("\n📥 Downloading from Icons8...\n")
        
        # Icons8 icon definitions: (icon_id, filename, color)
        icons = [
            # Price Management
            ("save", "save.png", "4CAF50"),
            ("plus-math", "add.png", "4CAF50"),
            ("checkmark", "apply.png", "009688"),
            ("export-csv", "export.png", "2196F3"),
            ("search", "filter.png", "FF9800"),
            ("reset", "reset.png", "F44336"),
            ("refresh", "refresh.png", "9C27B0"),
            ("combo-chart", "chart.png", "2196F3"),
            
            # Portfolio Management
            ("briefcase", "portfolio.png", "3F51B5"),
            ("add-shopping-cart", "buy.png", "4CAF50"),
            ("sell", "sell.png", "F44336"),
            ("transaction", "transaction.png", "FFC107"),
            ("profit", "profit.png", "4CAF50"),
            ("loss", "loss.png", "F44336"),
            ("info", "details.png", "607D8B"),
        ]
        
        for icon_id, filename, color in icons:
            url = f"https://img.icons8.com/{button_size}/{color}/{icon_id}.png"
            try:
                filepath = self.icons_dir / filename
                request = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(request, timeout=20) as response:
                    content = response.read()

                raw_img = Image.open(io.BytesIO(content))
                normalized = self._normalize_icon_image(
                    raw_img,
                    target_size=button_size,
                    padding=1,
                    vertical_offset=0
                )
                normalized.save(filepath, format='PNG')
                print(f"✅ Downloaded: {filename} ({button_size}x{button_size})")
            except Exception as e:
                print(f"❌ Failed {filename}: {e}")
        
        # Create app icon separately
        self._create_app_icon()
        
        print("\n⚠️  WICHTIG: Icons8 Attribution erforderlich!")
        print("Add to README.md: Icons by Icons8 (https://icons8.com)")


def main():
    """Main setup function"""
    setup = IconSetup()
    
    print("\nWelche Icon-Größe möchtest du für Buttons?")
    print("1. 16x16 px (klein, für kompakte UI)")
    print("2. 24x24 px (empfohlen, gute Balance)")
    print("3. 32x32 px (groß, gut sichtbar)")
    
    choice = input("\nDeine Wahl (1-3) [Standard: 2]: ").strip() or "2"
    
    size_map = {"1": 16, "2": 24, "3": 32}
    button_size = size_map.get(choice, 24)
    
    print("\nWie möchtest du die Icons erstellen?")
    print("1. Selbst erstellen mit PIL (keine Attribution nötig)")
    print("2. Von Icons8 herunterladen (Attribution erforderlich)")
    
    method = input("\nDeine Wahl (1-2) [Standard: 1]: ").strip() or "1"
    
    if method == "2":
        setup.download_from_icons8(button_size)
    else:
        setup.create_all_icons(button_size)
    
    print("\n✨ Setup abgeschlossen! Starte deine App mit: python main.py")


if __name__ == "__main__":
    main()