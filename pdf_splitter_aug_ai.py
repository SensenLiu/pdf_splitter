# -*- coding: utf-8 -*-
import os
import re
import base64
import argparse
from pathlib import Path
from openai import OpenAI  # 通义千问完全兼容 OpenAI SDK
import pdfplumber
import PyPDF2

class QwenPDFSplitter:
    def __init__(self, args):
        self.input_pdf = Path(args.input).resolve()
        self.output_dir = Path(args.output).resolve()
        self.toc_pages = [int(p) for p in args.toc_pages.split(',')]
        self.first_phys = args.first_phys_page
        self.first_toc = args.first_toc_page
        self.skip_suffix = args.skip_suffix
        self.offset = self.first_phys - self.first_toc
        
        # === 阿里通义千问配置区 ===
        self.api_key = "sk-4d588fa63f2442f49d862efe29bf98ae"  # 替换为你的灵积 API Key
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1" # 阿里兼容接口地址
        self.model_name = "qwen-vl-plus" # 具有视觉能力的模型，推荐 qwen-vl-plus 或 qwen-vl-max
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # 初始化客户端
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def pdf_page_to_base64(self, page_obj):
        """将 PDF 页面转为图片并转码为 Base64"""
        img = page_obj.to_image(resolution=300)
        img_path = "temp_toc.png"
        img.save(img_path)
        with open(img_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def get_toc_from_ai(self):
        """调用通义千问 Vision 模型识别目录"""
        print(f"\n=== 步骤 1: 调用通义千问识别目录 (页码: {self.toc_pages}) ===")
        all_ai_content = ""
        
        with pdfplumber.open(self.input_pdf) as pdf:
            for p_num in self.toc_pages:
                print(f"正在上传物理第 {p_num} 页至通义千问进行视觉识别...")
                base64_image = self.pdf_page_to_base64(pdf.pages[p_num - 1])
                
                # 通义千问多模态调用
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text", 
                                    "text": "你是一个图书目录提取专家。请识别图中目录，利用常识纠正OCR识别错误（如将'各班洗艺'纠正为'鲁班学艺'）。严格按'标题 | 页码'格式输出，不要任何解释。"
                                },
                                {
                                    "type": "image_url", 
                                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                                }
                            ],
                        }
                    ],
                )
                all_ai_content += response.choices[0].message.content + "\n"
        
        print("\n--- 通义千问识别结果 ---")
        print(all_ai_content.strip())
        return all_ai_content

    def parse_ai_text(self, text):
        """解析 AI 返回的文本"""
        chapters = []
        for line in text.split('\n'):
            line = line.strip()
            if not line: continue
            # 兼容多种分隔符：|、/、空格
            match = re.search(r'(.+?)\s*[|｜/／]\s*(\d+)$', line) or re.search(r'(.+?)\s+(\d+)$', line)
            if match:
                title = re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]', '', match.group(1))
                toc_p = int(match.group(2))
                if len(title) >= 2:
                    chapters.append({"title": title, "phys_p": toc_p + self.offset})
        
        chapters.sort(key=lambda x: x['phys_p'])
        unique = []
        for c in chapters:
            if not unique or c['phys_p'] > unique[-1]['phys_p']:
                unique.append(c)
        return unique

    def split_pdf(self, chapters):
        """执行拆分逻辑并应用 skip_suffix"""
        print(f"\n=== 步骤 2: 执行拆分 (每章末尾减去 {self.skip_suffix} 页) ===")
        with open(self.input_pdf, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            total = len(reader.pages)
            for i, curr in enumerate(chapters):
                start = curr['phys_p']
                if i < len(chapters) - 1:
                    raw_end = chapters[i+1]['phys_p'] - 1 - self.skip_suffix
                    end = max(start, raw_end)
                else:
                    end = total
                
                if start > total or start > end: continue
                
                writer = PyPDF2.PdfWriter()
                for p_idx in range(start - 1, end):
                    writer.add_page(reader.pages[p_idx])
                
                # 清洗文件名
                safe_title = "".join(x for x in curr['title'] if x.isalnum())
                name = f"{i+1:02d}_{safe_title}.pdf"
                with open(self.output_dir / name, "wb") as out_f:
                    writer.write(out_f)
                print(f"成功保存: {name} (物理页: {start}-{end})")

    def run(self):
        ai_text = self.get_toc_from_ai()
        chapters = self.parse_ai_text(ai_text)
        if chapters:
            self.split_pdf(chapters)
            print(f"\n🎉 通义千问辅助拆分完成！输出目录: {self.output_dir}")
        else:
            print("\n❌ 未识别到有效目录，请检查图片清晰度或 API 配置。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True)
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--toc-pages", required=True)
    parser.add_argument("--first-toc-page", type=int, required=True)
    parser.add_argument("--first-phys-page", type=int, required=True)
    parser.add_argument("--skip-suffix", type=int, default=0)
    parser.add_argument("--use-ocr", action="store_true")

    args = parser.parse_args()
    QwenPDFSplitter(args).run()