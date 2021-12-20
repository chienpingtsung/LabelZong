import argparse
import tkinter
from pathlib import Path

import numpy as np
from PIL import Image, ImageTk, ImageDraw


class LabelZong(tkinter.Tk):
    def __init__(self):
        super(LabelZong, self).__init__()

        args = self.parse_args()
        self.trans = args.transparency
        self.brush = args.brush
        self.dataset_image = Path(args.dataset).joinpath('images/')
        self.dataset_mask = Path(args.dataset).joinpath('masks/')

        self.stems = self.prepare_dataset()
        self.index = 0

        # North frame
        self.frame_n = tkinter.Frame(self)
        self.frame_n.pack(expand=True, fill='both')
        self.canvas = tkinter.Canvas(self.frame_n, highlightthickness=0)
        self.canvas.pack()

        # Center frame
        self.frame_c = tkinter.Frame(self)
        self.frame_c.pack()
        self.scale = tkinter.Scale(self.frame_c, orient=tkinter.HORIZONTAL)
        self.scale.set(int(self.trans * 100))
        self.scale.pack()

        # South frame
        self.frame_s = tkinter.Frame(self)
        self.frame_s.pack()
        self.prev_butt = tkinter.Button(self.frame_s, text='Prev')
        self.prev_butt.grid(column=0, row=0)
        self.next_butt = tkinter.Button(self.frame_s, text='Next')
        self.next_butt.grid(column=1, row=0)
        self.clean_butt = tkinter.Button(self.frame_s, text='Clean')
        self.clean_butt.grid(column=2, row=0)
        self.reset_butt = tkinter.Button(self.frame_s, text='Reset')
        self.reset_butt.grid(column=3, row=0)

        # Zoomed window
        self.state('zoomed')

        # Display init
        self.image = None
        self.mask = None
        self.dye = None
        self.brush_mask = None
        self.brush_dye = None
        self.zoom = None
        self.photo_image = None
        self.load()

        # Events binding
        self.frame_n.bind('<Configure>', self.on_window_change)
        self.canvas.bind('<Motion>', self.canvas_motion)
        self.canvas.bind('<B1-Motion>', self.canvas_motion)
        self.canvas.bind('<MouseWheel>', self.canvas_wheel)
        self.scale.configure(command=self.scale_change)
        self.prev_butt.configure(command=self.prev_event)
        self.next_butt.configure(command=self.next_event)
        self.clean_butt.configure(command=self.clean_event)
        self.reset_butt.configure(command=self.reset_event)

    def reset_event(self):
        self.load()

    def clean_event(self):
        self.mask = Image.new('L', self.mask.size, color=0)
        self.photo_image = self.prepare_photo_image(self.brush_mask)
        self.render()

    def next_event(self):
        self.mask.convert('1').save(self.dataset_mask.joinpath(f'{self.stems[self.index]}.png'))
        if self.index == len(self.stems) - 1:
            return
        self.index += 1
        self.load()

    def prev_event(self):
        if self.index == 0:
            return
        self.index -= 1
        self.load()

    def load(self):
        self.title(f'LabelZong ({self.index + 1}/{len(self.stems)})')
        self.image, self.mask, self.dye, self.brush_mask, self.brush_dye = self.prepare_image_mask_dye()
        self.on_window_change()
        self.photo_image = self.prepare_photo_image(self.brush_mask)
        self.render()

    def scale_change(self, event):
        self.trans = int(event) / 100
        self.photo_image = self.prepare_photo_image(self.brush_mask)
        self.render()

    def canvas_wheel(self, event):
        if event.delta < 0:
            self.brush -= 2
        else:
            self.brush += 2
        self.canvas_motion(event)

    def canvas_motion(self, event):
        x, y = event.x / self.zoom, event.y / self.zoom
        if event.state & 256:
            self.draw_mask(self.mask, x, y, fill=0, outline=0)
        brush_mask = self.brush_mask.copy()
        self.draw_mask(brush_mask, x, y, fill=0, outline=255)
        self.photo_image = self.prepare_photo_image(brush_mask)
        self.render()

    def draw_mask(self, mask, x, y, fill=None, outline=None):
        draw = ImageDraw.Draw(mask)
        draw.pieslice(((x - self.brush, y - self.brush), (x + self.brush, y + self.brush)),
                      start=0, end=360, fill=fill, outline=outline)

    def on_window_change(self, evnet=None):
        self.zoom = self.calculate_zoom()
        self.photo_image = self.prepare_photo_image(self.brush_mask)
        self.canvas.configure(width=self.photo_image.width(), height=self.photo_image.height())
        self.render()

    def parse_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('-t', '--transparency', default=0.2, type=float)
        parser.add_argument('-b', '--brush', default=20, type=int)
        parser.add_argument('dataset')
        return parser.parse_args()

    def prepare_dataset(self):
        image_stems = {p.stem for p in self.dataset_image.glob('*.png')}
        mask_stems = {p.stem for p in self.dataset_mask.glob('*.png')}
        assert not image_stems - mask_stems, f'missing masks of images: {image_stems - mask_stems}'
        assert not mask_stems - image_stems, f'missing images of masks: {mask_stems - image_stems}'
        assert image_stems, f'empty dataset'
        return sorted(list(image_stems))

    def prepare_image_mask_dye(self):
        image = Image.open(self.dataset_image.joinpath(f'{self.stems[self.index]}.png')).convert('RGB')
        mask = Image.open(self.dataset_mask.joinpath(f'{self.stems[self.index]}.png')).convert('L')
        dye = Image.new('RGB', mask.size, (255, 0, 0))
        brush_mask = Image.new('L', mask.size, 0)
        brush_dye = Image.new('RGB', mask.size, (0, 255, 0))
        return image, mask, dye, brush_mask, brush_dye

    def prepare_photo_image(self, brush_mask):
        mask = np.uint8(np.array(self.mask) * self.trans)
        mask = Image.fromarray(mask, 'L')
        image = self.image.copy()
        image.paste(im=self.dye, mask=mask)
        image.paste(im=self.brush_dye, mask=brush_mask)
        w, h = image.size
        image = image.resize((int(w * self.zoom), int(h * self.zoom)))
        return ImageTk.PhotoImage(image)

    def calculate_zoom(self):
        self.update()
        winw, winh = self.frame_n.winfo_width(), self.frame_n.winfo_height()
        w, h = self.image.size
        if winw / winh < w / h:
            return winw / w
        return winh / h

    def render(self):
        self.canvas.delete(tkinter.ALL)
        self.canvas.create_image(0, 0, anchor=tkinter.NW, image=self.photo_image)


if __name__ == '__main__':
    root = LabelZong()
    root.mainloop()
