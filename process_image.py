import os
import re
import time
import json

import tqdm
from PIL import Image, ImageDraw, ImageFont
from googletrans import Translator

class ImageTranslator:
    def __init__(self, image_path, annotations, font_path, debug_mode=False):
        self.image_path = image_path
        self.img = Image.open(self.image_path).copy()
        self.debug_img = self.img.copy() if debug_mode else None
        self.annotations = annotations
        self.font_path = font_path
        self.debug_mode = debug_mode
        self.translator = Translator()

    def is_numeric(self, text):
        return bool(re.fullmatch(r'^[0-9\s.]+$', text))

    def translate_text(self, text):
        if text.strip() == '':
            return text
        if self.is_numeric(text):
            return float(text)
        if text is None:
            return ' '
        for _ in range(3):  # 최대 3회 시도
            try:
                translated = self.translator.translate(text, src='en', dest='ko')
                return translated.text
            except Exception as e:  # 예외 발생 시
                print(f"Error encountered: {e}. Retrying...")
                time.sleep(1)  # 1초 대기
        # 3회 시도 후에도 실패할 경우 에러 메시지 반환
        print("Translation failed after multiple attempts.")
        return text
        
    def draw_bbox_translate_text(self, draw, text, bbox):
        if self.is_numeric(text):  # If the text is numeric, return as it is.
            return text
        else:
            translated_text = self.translate_text(text)
            draw.rectangle([(bbox["x"], bbox["y"]), (bbox["x"] + bbox["w"], bbox["y"] + bbox["h"])], fill="white")
            if bbox["w"] > bbox["h"]:
                font = ImageFont.truetype(self.font_path, int(bbox["h"] * 0.7))
                draw.text((bbox["x"], bbox["y"]), translated_text, font=font, fill="black")
            else:
                # Create a new image with transparent background to draw the rotated text
                text_img = Image.new('RGBA', (int(bbox["h"]), int(bbox["h"])), (255, 255, 255, 0))
                font = ImageFont.truetype(self.font_path, int(bbox["w"] * 0.7))
                text_draw = ImageDraw.Draw(text_img)
                text_draw.text((0, 0), translated_text, font=font, fill="black")
                # Rotate the text image and then paste it on the original image
                rotated_text_img = text_img.rotate(90, expand=True)
                draw.bitmap((bbox["x"], bbox["y"]), rotated_text_img, fill="black")
            return translated_text

    def draw_translated_text(self):
        draw = ImageDraw.Draw(self.img)

        # General Figure Info
        general_figure_info = data['general_figure_info']
        
        # title bbox
        if 'title' in general_figure_info and 'bbox' in general_figure_info['title']:
            text = general_figure_info['title']['text']
            bbox = general_figure_info['title']['bbox']
            translated_text = self.draw_bbox_translate_text(draw, text, bbox)
            general_figure_info['title']['text'] = translated_text

        # Legend
        if 'legend' in general_figure_info:
            for item in general_figure_info['legend'].get('items', []):
                text = item['label']['text']
                bbox = item['label']['bbox']
                translated_text = self.draw_bbox_translate_text(draw, text, bbox)
                item['label']['text'] = translated_text
                item['model'] = translated_text
                for model in data.get('models', []):
                    if model['name'] == text:
                        model['name'] = translated_text
                        model['label'] = translated_text
        
        # x and y ticks, labels and other components
        for axis in ['x_axis', 'y_axis']:
            for key in ['major_labels', 'rule', 'label']:
                if key in general_figure_info[axis]:
                    if key == 'label' and 'bbox' in general_figure_info[axis][key]:
                        text = general_figure_info[axis][key]['text']
                        bbox = general_figure_info[axis][key]['bbox']
                        translated_text = self.draw_bbox_translate_text(draw, text, bbox)
                        general_figure_info[axis][key]['text'] = translated_text
                    else:
                        values = general_figure_info[axis][key].get('values', [])
                        translated_values = [self.translate_text(value) for value in values]  # 모든 값을 번역
                        general_figure_info[axis][key]['values'] = translated_values  # 번역된 텍스트들로 업데이트
                        bboxes = general_figure_info[axis][key].get('bboxes', [])
                        
                        # 'values'와 'bboxes'가 모두 존재하고 동일한 길이를 가질 때만 bounding box를 그립니다
                        if values and bboxes and len(values) == len(bboxes):
                            for bbox, value in zip(bboxes, values):
                                self.draw_bbox_translate_text(draw, value, bbox)

    def save_image(self, path):
        self.img.save(path)

    def show_image(self):
        self.img.show()

if __name__ == "__main__":
    source_folder = "../data/test/png"
    target_root_folder = "../data/translated_test/png"
    source_annotation_file = "../data/test/annotations.json"
    target_annotation_file = "../data/translated_test/annotations.json"
    font_path = "./font/휴먼명조.ttf"

    os.makedirs(target_root_folder, exist_ok=True)

    image_list = sorted(os.listdir(source_folder), key=lambda x: int(x.split('.')[0]))

    with open(source_annotation_file, "r") as file:
        datas = json.load(file)

    assert len(image_list) == len(datas)

    with open(target_annotation_file, "w") as out_file:
        out_file.write("[\n")
        with tqdm.tqdm(zip(image_list, datas), total=len(image_list)) as pbar:
            for image_path, data in pbar:
                try:
                    translator = ImageTranslator(os.path.join(source_folder, image_path), data, font_path)
                    translator.draw_translated_text()
                    translator.save_image(os.path.join(target_root_folder, image_path))
                    
                    json.dump(data, out_file, ensure_ascii=False, indent=4)
                    out_file.write(",\n")
                except:
                    print(f"Error encountered while processing {image_path}")
        out_file.write("\n]")

