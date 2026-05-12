from __future__ import annotations

import argparse
import tkinter as tk
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from PIL import Image, ImageDraw, ImageTk

from kegg.formats.bob import parse_bob_header
from kegg.formats.cod import decode_file
from kegg.graphics.bob_preview import bob_preview_info, make_raw_bob_atlas
from kegg.formats.level import BRICK_GRID_HEIGHT, BRICK_GRID_WIDTH, load_level_set, parse_render_levels
from kegg.graphics.level_preview import BRICK_STEP_H, BRICK_STEP_W, make_level_preview, make_game_level_preview


class ScrollableImage(ttk.Frame):
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg="#202020", highlightthickness=0)
        self.xbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.ybar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.xbar.set, yscrollcommand=self.ybar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.ybar.grid(row=0, column=1, sticky="ns")
        self.xbar.grid(row=1, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._photo: Optional[ImageTk.PhotoImage] = None

    def set_image(self, image: Image.Image) -> None:
        self._photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        self.canvas.configure(scrollregion=(0, 0, image.width, image.height))


class SpriteAtlasTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, data_dir: Path) -> None:
        super().__init__(parent)
        self.data_dir = data_dir
        self._build_ui()
        self.refresh_files()

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, padding=8)
        left.grid(row=0, column=0, sticky="ns")
        ttk.Label(left, text="Sprite / image files").pack(anchor="w")
        self.file_list = tk.Listbox(left, width=28, height=28, exportselection=False)
        self.file_list.pack(fill="y", expand=True, pady=(4, 8))
        self.file_list.bind("<<ListboxSelect>>", lambda _event: self.show_selected())
        ttk.Button(left, text="Refresh", command=self.refresh_files).pack(fill="x")

        right = ttk.Frame(self, padding=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        self.info = tk.Text(right, height=7, wrap="word")
        self.info.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.info.configure(state="disabled")
        self.preview = ScrollableImage(right)
        self.preview.grid(row=1, column=0, sticky="nsew")

    def refresh_files(self) -> None:
        self.file_list.delete(0, tk.END)
        for path in sorted(self.data_dir.glob("*")):
            if path.suffix.upper() in {".BOB", ".GIF"}:
                self.file_list.insert(tk.END, path.name)
        if self.file_list.size():
            self.file_list.selection_set(0)
            self.show_selected()

    def _set_info(self, text: str) -> None:
        self.info.configure(state="normal")
        self.info.delete("1.0", tk.END)
        self.info.insert("1.0", text)
        self.info.configure(state="disabled")

    def show_selected(self) -> None:
        selection = self.file_list.curselection()
        if not selection:
            return
        path = self.data_dir / self.file_list.get(selection[0])
        try:
            if path.suffix.upper() == ".GIF":
                decoded = decode_file(path).data
                image = Image.open(BytesIO(decoded)).convert("RGBA")
                self._set_info(f"{path.name}\nDecoded as GIF. Size: {image.width} x {image.height}\nThis path is already real image decoding, not a raw guess.")
                self.preview.set_image(image.resize((image.width * 2, image.height * 2), Image.Resampling.NEAREST))
            elif path.suffix.upper() == ".BOB":
                header = parse_bob_header(path)
                info = bob_preview_info(path)
                text = (
                    f"{info.file_name}\n"
                    f"objects: {info.object_count}\n"
                    f"logical sprite size: {info.width} x {info.height}\n"
                    f"header size: {info.header_size}\n"
                    f"payload size: {info.payload_size}\n"
                    f"bounds: left={header.bounds_left}, top={header.bounds_top}, right={header.bounds_right}, bottom={header.bounds_bottom}\n"
                    f"note: {info.note}"
                )
                self._set_info(text)
                self.preview.set_image(make_raw_bob_atlas(path, self.data_dir, scale=3))
        except Exception as exc:
            messagebox.showerror("Preview error", str(exc))



class LevelViewTab(ttk.Frame):
    PREVIEW_SCALE = 4

    def __init__(self, parent: tk.Widget, data_dir: Path) -> None:
        super().__init__(parent)
        self.data_dir = data_dir
        self.levels = load_level_set(data_dir)
        self.render_levels = parse_render_levels(data_dir / "KE_LDCWC.TAB")
        self.level_var = tk.IntVar(value=min(2, len(self.render_levels)))
        self.view_var = tk.StringVar(value="game")
        self.show_grid_var = tk.BooleanVar(value=False)
        self.show_ids_var = tk.BooleanVar(value=False)
        self.show_spells_var = tk.BooleanVar(value=False)
        self.selected_cell_text = "Click a brick cell to inspect it."
        self._build_ui()
        self.level_var.trace_add("write", lambda *_args: self.after_idle(self.render_level))
        self.render_level()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=8)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(toolbar, text="Level").pack(side="left")
        spin = ttk.Spinbox(
            toolbar,
            from_=1,
            to=max(1, len(self.render_levels)),
            width=5,
            textvariable=self.level_var,
        )
        spin.pack(side="left", padx=(4, 12))
        spin.bind("<Return>", lambda _event: self.render_level())
        spin.bind("<FocusOut>", lambda _event: self.render_level())

        ttk.Label(toolbar, text="View").pack(side="left")
        view_box = ttk.Combobox(
            toolbar,
            width=14,
            textvariable=self.view_var,
            values=["game", "spells", "bricks"],
            state="readonly",
        )
        view_box.pack(side="left", padx=(4, 12))
        view_box.bind("<<ComboboxSelected>>", lambda _event: self.render_level())

        self.preview = ScrollableImage(self)
        self.preview.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(0, 8))
        self.preview.canvas.bind("<Button-1>", self.on_preview_click)

        side = ttk.Frame(self, padding=8)
        side.grid(row=1, column=1, sticky="nswe", padx=(4, 8), pady=(0, 8))
        side.columnconfigure(0, weight=1)

        ttk.Label(side, text="Display").grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(side, text="Grid overlay", variable=self.show_grid_var, command=self.render_level).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(side, text="Brick image ids overlay", variable=self.show_ids_var, command=self.render_level).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(side, text="Spell icons overlay", variable=self.show_spells_var, command=self.render_level).grid(row=3, column=0, sticky="w")

        ttk.Separator(side).grid(row=4, column=0, sticky="ew", pady=8)

        self.info = tk.Text(side, width=44, height=28, wrap="word")
        self.info.grid(row=5, column=0, sticky="nsew")
        self.info.configure(state="disabled")
        side.rowconfigure(5, weight=1)

    def _set_info(self, text: str) -> None:
        self.info.configure(state="normal")
        self.info.delete("1.0", tk.END)
        self.info.insert("1.0", text)
        self.info.configure(state="disabled")

    def _current_level_number(self) -> int:
        return max(1, min(self.level_var.get(), len(self.render_levels)))

    def _cell_at_image_xy(self, image_x: float, image_y: float):
        x = int(image_x) // (BRICK_STEP_W * self.PREVIEW_SCALE)
        y = int(image_y) // (BRICK_STEP_H * self.PREVIEW_SCALE)
        if 0 <= x < BRICK_GRID_WIDTH and 0 <= y < BRICK_GRID_HEIGHT:
            level = self.render_levels[self._current_level_number() - 1]
            return level.cells[y * BRICK_GRID_WIDTH + x]
        return None

    def on_preview_click(self, event: tk.Event) -> None:
        image_x = self.preview.canvas.canvasx(event.x)
        image_y = self.preview.canvas.canvasy(event.y)
        cell = self._cell_at_image_xy(image_x, image_y)
        if cell is None:
            self.selected_cell_text = f"Clicked outside level grid at image x={int(image_x)}, y={int(image_y)}."
        else:
            sprite_id = cell.brick_sprite_id
            powerup = cell.powerup_spell_id
            spell_name = cell.powerup_spell_name
            self.selected_cell_text = (
                f"Selected cell\n"
                f"  position: x={cell.x}, y={cell.y}\n"
                f"  linear index: {cell.y * BRICK_GRID_WIDTH + cell.x}\n"
                f"  raw word: 0x{cell.raw_word:04x}\n"
                f"  stored brick id: {cell.brick_id}\n"
                f"  rendered KE_BRICK.BOB image: {sprite_id if sprite_id is not None else 'empty'}\n"
                f"  brick class: {cell.brick_class}\n"
                f"  can contain powerup: {cell.can_contain_powerup}\n"
                f"  low byte / metadata: {cell.flags} (0x{cell.flags:02x})\n"
                f"  EXE drop type: {cell.powerup_drop_type if cell.powerup_drop_type is not None else 'none'}\n"
                f"  variant bits: {cell.powerup_variant if cell.powerup_variant is not None else 'none'}\n"
                f"  game spell frames: {cell.powerup_frames if cell.powerup_frames is not None else 'none'}\n"
                f"  representative game frame: {powerup if powerup is not None else 'none'}\n"
                f"  actual KE_SPELL.BOB image: {cell.powerup_spell_bob_sprite_index if cell.powerup_spell_bob_sprite_index is not None else 'none'}\n"
                f"  logical spell: {spell_name if spell_name is not None else 'none'}\n"
            )
        self.render_level()

    def render_level(self) -> None:
        number = self._current_level_number()
        view = self.view_var.get()

        if view == "game":
            image = make_game_level_preview(
                self.data_dir,
                number=number,
                scale=self.PREVIEW_SCALE,
                show_grid=self.show_grid_var.get(),
                show_ids=self.show_ids_var.get(),
                show_spells=self.show_spells_var.get(),
            )
            self.preview.set_image(image)
            level = self.render_levels[number - 1]
            nonzero = sum(1 for cell in level.cells if cell.raw_word)
            powerups = sum(1 for cell in level.cells if cell.powerup_spell_id is not None)
            info = (
                f"Gameplay view\n"
                f"Level {number:02d}: {nonzero}/270 occupied cells.\n"
                f"Known powerup/drop code cells: {powerups}.\n\n"
                f"Overlay drawing is applied after scaling so ids and spell icons stay readable.\n"
                f"{self.selected_cell_text}"
            )
        elif view == "spells":
            image = make_level_preview(self.data_dir, number=number, view="spells", scale=3)
            self.preview.set_image(image)
            logic = self.levels.logic_levels[number - 1]
            layer = logic.layers[0]
            nonzero = sum(1 for value in layer if value)
            info = (
                f"Spells / low-byte codes\n"
                f"Level {number:02d}: {nonzero}/270 non-zero cells.\n"
                f"This is the raw low-byte grid from KE_LDCWC.TAB used for spell/drop metadata."
            )
        elif view == "bricks":
            image = make_level_preview(self.data_dir, number=number, view="bricks", scale=3)
            self.preview.set_image(image)
            logic = self.levels.logic_levels[number - 1]
            layer = logic.layers[1]
            nonzero = sum(1 for value in layer if value)
            info = (
                f"Bricks / high-byte ids\n"
                f"Level {number:02d}: {nonzero}/270 non-zero cells.\n"
                f"This is the raw high-byte grid from KE_LDCWC.TAB used as 1-based KE_BRICK.BOB ids."
            )
        else:
            image = make_game_level_preview(self.data_dir, number=number, scale=self.PREVIEW_SCALE)
            self.preview.set_image(image)
            info = f"Unknown view '{view}', falling back to gameplay render for level {number:02d}."

        self._set_info(info)


class SpriteAtlasTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, data_dir: Path) -> None:
        super().__init__(parent)
        self.data_dir = data_dir
        self._build_ui()
        self.refresh_files()

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, padding=8)
        left.grid(row=0, column=0, sticky="ns")
        ttk.Label(left, text="Sprite / image files").pack(anchor="w")
        self.file_list = tk.Listbox(left, width=28, height=28, exportselection=False)
        self.file_list.pack(fill="y", expand=True, pady=(4, 8))
        self.file_list.bind("<<ListboxSelect>>", lambda _event: self.show_selected())
        ttk.Button(left, text="Refresh", command=self.refresh_files).pack(fill="x")

        right = ttk.Frame(self, padding=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        self.info = tk.Text(right, height=7, wrap="word")
        self.info.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.info.configure(state="disabled")
        self.preview = ScrollableImage(right)
        self.preview.grid(row=1, column=0, sticky="nsew")

    def refresh_files(self) -> None:
        self.file_list.delete(0, tk.END)
        for path in sorted(self.data_dir.glob("*")):
            if path.suffix.upper() in {".BOB", ".GIF"}:
                self.file_list.insert(tk.END, path.name)
        if self.file_list.size():
            self.file_list.selection_set(0)
            self.show_selected()

    def _set_info(self, text: str) -> None:
        self.info.configure(state="normal")
        self.info.delete("1.0", tk.END)
        self.info.insert("1.0", text)
        self.info.configure(state="disabled")

    def show_selected(self) -> None:
        selection = self.file_list.curselection()
        if not selection:
            return
        path = self.data_dir / self.file_list.get(selection[0])
        try:
            if path.suffix.upper() == ".GIF":
                decoded = decode_file(path).data
                image = Image.open(BytesIO(decoded)).convert("RGBA")
                self._set_info(f"{path.name}\nDecoded as GIF. Size: {image.width} x {image.height}\nThis path is already real image decoding, not a raw guess.")
                self.preview.set_image(image.resize((image.width * 2, image.height * 2), Image.Resampling.NEAREST))
            elif path.suffix.upper() == ".BOB":
                header = parse_bob_header(path)
                info = bob_preview_info(path)
                text = (
                    f"{info.file_name}\n"
                    f"objects: {info.object_count}\n"
                    f"logical sprite size: {info.width} x {info.height}\n"
                    f"header size: {info.header_size}\n"
                    f"payload size: {info.payload_size}\n"
                    f"bounds: left={header.bounds_left}, top={header.bounds_top}, right={header.bounds_right}, bottom={header.bounds_bottom}\n"
                    f"note: {info.note}"
                )
                self._set_info(text)
                self.preview.set_image(make_raw_bob_atlas(path, self.data_dir, scale=3))
        except Exception as exc:
            messagebox.showerror("Preview error", str(exc))


class LevelViewTab(ttk.Frame):
    PREVIEW_SCALE = 4

    def __init__(self, parent: tk.Widget, data_dir: Path) -> None:
        super().__init__(parent)
        self.data_dir = data_dir
        self.levels = load_level_set(data_dir)
        self.render_levels = parse_render_levels(data_dir / "KE_LDCWC.TAB")
        self.level_var = tk.IntVar(value=min(2, len(self.render_levels)))
        self.view_var = tk.StringVar(value="game")
        self.show_grid_var = tk.BooleanVar(value=False)
        self.show_ids_var = tk.BooleanVar(value=False)
        self.show_spells_var = tk.BooleanVar(value=False)
        self.selected_cell_text = "Click a brick cell to inspect it."
        self._build_ui()
        self.render_level()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=8)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(toolbar, text="Level").pack(side="left")
        ttk.Spinbox(
            toolbar,
            from_=1,
            to=max(1, len(self.render_levels)),
            width=5,
            textvariable=self.level_var,
            command=self.render_level,
        ).pack(side="left", padx=(4, 12))

        ttk.Label(toolbar, text="View").pack(side="left")
        view_box = ttk.Combobox(
            toolbar,
            width=12,
            textvariable=self.view_var,
            values=["game", "visual", "logic0", "logic1"],
            state="readonly",
        )
        view_box.pack(side="left", padx=(4, 12))
        view_box.bind("<<ComboboxSelected>>", lambda _event: self.render_level())
        ttk.Button(toolbar, text="Render", command=self.render_level).pack(side="left")

        self.preview = ScrollableImage(self)
        self.preview.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(0, 8))
        self.preview.canvas.bind("<Button-1>", self.on_preview_click)

        side = ttk.Frame(self, padding=8)
        side.grid(row=1, column=1, sticky="nswe", padx=(4, 8), pady=(0, 8))
        side.columnconfigure(0, weight=1)

        ttk.Label(side, text="Display").grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(side, text="Grid", variable=self.show_grid_var, command=self.render_level).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(side, text="Brick image ids", variable=self.show_ids_var, command=self.render_level).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(side, text="Show spells / drops", variable=self.show_spells_var, command=self.render_level).grid(row=3, column=0, sticky="w")

        ttk.Separator(side).grid(row=4, column=0, sticky="ew", pady=8)

        self.info = tk.Text(side, width=42, height=28, wrap="word")
        self.info.grid(row=5, column=0, sticky="nsew")
        self.info.configure(state="disabled")
        side.rowconfigure(5, weight=1)

    def _set_info(self, text: str) -> None:
        self.info.configure(state="normal")
        self.info.delete("1.0", tk.END)
        self.info.insert("1.0", text)
        self.info.configure(state="disabled")

    def _current_level_number(self) -> int:
        return max(1, min(self.level_var.get(), len(self.render_levels)))

    def _cell_at_image_xy(self, image_x: float, image_y: float):
        x = int(image_x) // (BRICK_STEP_W * self.PREVIEW_SCALE)
        y = int(image_y) // (BRICK_STEP_H * self.PREVIEW_SCALE)
        if 0 <= x < BRICK_GRID_WIDTH and 0 <= y < BRICK_GRID_HEIGHT:
            level = self.render_levels[self._current_level_number() - 1]
            return level.cells[y * BRICK_GRID_WIDTH + x]
        return None

    def on_preview_click(self, event: tk.Event) -> None:
        # Convert visible canvas coordinates to image coordinates, including scroll offset.
        image_x = self.preview.canvas.canvasx(event.x)
        image_y = self.preview.canvas.canvasy(event.y)
        cell = self._cell_at_image_xy(image_x, image_y)
        if cell is None:
            self.selected_cell_text = f"Clicked outside level grid at image x={int(image_x)}, y={int(image_y)}."
        else:
            sprite_id = cell.brick_sprite_id
            powerup = cell.powerup_spell_id
            spell_name = cell.powerup_spell_name
            self.selected_cell_text = (
                f"Selected cell\n"
                f"  position: x={cell.x}, y={cell.y}\n"
                f"  linear index: {cell.y * BRICK_GRID_WIDTH + cell.x}\n"
                f"  raw word: 0x{cell.raw_word:04x}\n"
                f"  stored brick id: {cell.brick_id}\n"
                f"  rendered KE_BRICK.BOB image: {sprite_id if sprite_id is not None else 'empty'}\n"
                f"  brick class: {cell.brick_class}\n"
                f"  can contain powerup: {cell.can_contain_powerup}\n"
                f"  low byte / metadata: {cell.flags} (0x{cell.flags:02x})\n"
                f"  EXE drop type: {cell.powerup_drop_type if cell.powerup_drop_type is not None else 'none'}\n"
                f"  variant bits: {cell.powerup_variant if cell.powerup_variant is not None else 'none'}\n"
                f"  game spell frames: {cell.powerup_frames if cell.powerup_frames is not None else 'none'}\n"
                f"  representative game frame: {powerup if powerup is not None else 'none'}\n"
                f"  actual KE_SPELL.BOB image: {cell.powerup_spell_bob_sprite_index if cell.powerup_spell_bob_sprite_index is not None else 'none'}\n"
                f"  logical spell: {spell_name if spell_name is not None else 'none'}\n"
            )
        self.render_level()

    def render_level(self) -> None:
        number = self._current_level_number()
        view = self.view_var.get()

        if view == "game":
            image = make_game_level_preview(
                self.data_dir,
                number=number,
                scale=self.PREVIEW_SCALE,
                show_grid=self.show_grid_var.get(),
                show_ids=self.show_ids_var.get(),
                show_spells=self.show_spells_var.get(),
            )
            self.preview.set_image(image)
            level = self.render_levels[number - 1]
            nonzero = sum(1 for cell in level.cells if cell.raw_word)
            powerups = sum(1 for cell in level.cells if cell.powerup_spell_id is not None)
            info = (
                f"Gameplay view\n"
                f"Level {number:02d}: {nonzero}/270 occupied cells.\n"
                f"Known powerup/drop code cells: {powerups}.\n\n"
                f"Corrected brick indexing:\n"
                f"  stored high byte 0 = empty\n"
                f"  rendered KE_BRICK.BOB image = high byte - 1\n\n"
                f"{self.selected_cell_text}"
            )
        elif view == "visual":
            image = make_level_preview(self.data_dir, number=number, view=view, scale=3)
            self.preview.set_image(image)
            visual_number = min(number, len(self.levels.visual_levels))
            visual = self.levels.visual_levels[visual_number - 1]
            nonzero = sum(1 for value in visual.cells if value)
            info = (
                f"Raw KE_LVL.DIG visual/debug grid\n"
                f"Level {visual_number:02d}: {nonzero}/270 non-zero cells.\n\n"
                f"This is not the gameplay brick renderer."
            )
        elif view.startswith("logic") and view[-1].isdigit():
            image = make_level_preview(self.data_dir, number=number, view=view, scale=3)
            self.preview.set_image(image)
            layer_index = int(view[-1])
            logic = self.levels.logic_levels[number - 1]
            layer = logic.layers[layer_index]
            nonzero = sum(1 for value in layer if value)
            info = (
                f"Raw KE_LDCWC.TAB diagnostic layer\n"
                f"Level {number:02d}, logic layer {layer_index}: {nonzero}/270 non-zero cells.\n"
                f"logic0 = low bytes, logic1 = high bytes."
            )
        else:
            image = make_game_level_preview(self.data_dir, number=number, scale=self.PREVIEW_SCALE)
            self.preview.set_image(image)
            info = f"Unknown view '{view}', falling back to gameplay render for level {number:02d}."

        self._set_info(info)


class GraphicsOverviewTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, data_dir: Path) -> None:
        super().__init__(parent)
        self.data_dir = data_dir
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=8)
        toolbar.grid(row=0, column=0, sticky="ew")
        ttk.Label(toolbar, text="Combined atlas of all currently decoded graphics.").pack(side="left")
        ttk.Button(toolbar, text="Rebuild", command=self.refresh).pack(side="right")

        self.preview = ScrollableImage(self)
        self.preview.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.refresh()

    def refresh(self) -> None:
        out_dir = self.data_dir.parent / 'output' / 'graphics'
        out_path = build_graphics_overview(self.data_dir, out_dir)
        image = Image.open(out_path).convert('RGB')
        self.preview.set_image(image)


class NotesTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, docs_dir: Path) -> None:
        super().__init__(parent)
        self.docs_dir = docs_dir
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        text = tk.Text(self, wrap="word")
        text.grid(row=0, column=0, sticky="nsew")
        content = []
        for name in ["FORMAT_NOTES.md", "GUI_NOTES.md", "LEVEL_NOTES.md", "LEVEL_FORMAT.md", "BOB_FORMAT.md", "RESEARCH_NOTES.md", "POWERUPS.md"]:
            path = docs_dir / name
            if path.exists():
                content.append(f"# {name}\n\n{path.read_text(encoding='utf-8', errors='replace')}")
        text.insert("1.0", "\n\n".join(content) if content else "No docs found yet.")
        text.configure(state="disabled")


def make_level02_reference_guess(show_frame: bool = True) -> Image.Image:
    """Renders a hand-authored level-02-like grid for GUI calibration.

    This is not parsed game data yet. It exists so the editor has the same shape
    as the intended final tool: level canvas now, real level table later.
    """
    scale = 3
    cols = 18
    rows = 14
    brick_w = 15
    brick_h = 8
    gap_x = 2
    gap_y = 1
    left = 44 if show_frame else 8
    top = 63 if show_frame else 8
    width = 512 if show_frame else left * 2 + cols * (brick_w + gap_x)
    height = 340 if show_frame else top * 2 + rows * (brick_h + gap_y)
    image = Image.new("RGB", (width, height), (8, 45, 54))
    draw = ImageDraw.Draw(image)

    if show_frame:
        draw.rectangle((0, 0, width - 1, height - 1), fill=(35, 22, 13), outline=(0, 220, 255), width=2)
        draw.rectangle((20, 25, width - 20, height - 12), outline=(2, 117, 136), width=2)
        draw.text((24, 8), "SCORE: 000 120", fill=(180, 255, 180))
        draw.text((210, 8), "LEVEL : 02", fill=(255, 220, 120))
        draw.text((330, 8), "HIGH SCORE: 005000", fill=(180, 255, 180))

    for y in range(rows):
        for x in range(cols):
            # approximate visible level 02: red edges, yellow/orange center, dark side caps
            if x == 0 or x == cols - 1:
                color = (72, 47, 38)
            else:
                center = abs(x - (cols - 1) / 2) / ((cols - 1) / 2)
                vertical = abs(y - rows / 2) / (rows / 2)
                r = 210 + int(35 * (1 - vertical))
                g = 20 + int(180 * (1 - center) * (1 - vertical * 0.25))
                b = 10
                color = (min(r, 255), min(g, 230), b)
            bx = left + x * (brick_w + gap_x)
            by = top + y * (brick_h + gap_y)
            draw.rounded_rectangle((bx, by, bx + brick_w, by + brick_h), radius=2, fill=color, outline=(32, 18, 18))
            draw.line((bx + 2, by + 1, bx + brick_w - 4, by + 1), fill=(255, 140, 120))
            if x not in {0, cols - 1}:
                draw.point((bx - 1, by + brick_h // 2), fill=(0, 200, 255))
                draw.point((bx + brick_w + 1, by + brick_h // 2), fill=(0, 200, 255))

    if show_frame:
        panel_top = top + rows * (brick_h + gap_y) + 8
        for y in range(3):
            for x in range(9):
                px = left + x * 51
                py = panel_top + y * 38
                draw.rectangle((px, py, px + 48, py + 35), fill=(0, 77, 83), outline=(0, 114, 122))
                draw.rectangle((px + 14, py + 9, px + 28, py + 23), outline=(108, 230, 90), width=2)
        draw.rounded_rectangle((228, height - 38, 290, height - 26), radius=6, fill=(120, 85, 75), outline=(255, 220, 0))
        draw.ellipse((252, height - 49, 263, height - 38), fill=(255, 50, 0))

    return image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)


class KeggEditorApp(tk.Tk):
    def __init__(self, data_dir: Path) -> None:
        super().__init__()
        self.title("Krypton Egg reverse editor")
        self.geometry("1200x850")
        self.data_dir = data_dir
        self.docs_dir = Path("docs")
        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        header = ttk.Frame(self, padding=8)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Button(header, text="Change data directory…", command=self.change_data_dir).pack(side="right")

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew")
        notebook.add(LevelViewTab(notebook, self.data_dir), text="Level View")
        notebook.add(SpriteAtlasTab(notebook, self.data_dir), text="Sprite Atlas")

    def change_data_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=str(self.data_dir))
        if not selected:
            return
        # Simpler and safer for now: restart the app state around a new data dir.
        self.destroy()
        KeggEditorApp(Path(selected)).mainloop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the Krypton Egg reverse editor GUI")
    parser.add_argument("--data-dir", default="game_data", help="Directory containing the original game files")
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise SystemExit(f"Data directory does not exist: {data_dir}")
    app = KeggEditorApp(data_dir)
    app.mainloop()


if __name__ == "__main__":
    main()
