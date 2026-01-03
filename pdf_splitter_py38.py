# -*- coding: utf-8 -*-
# 强化目录识别、完整打印、最后章节页码边界修正PDF工具 (Python3.8, Conda环境兼容)

import sys
import argparse
from pathlib import Path
import re

try:
    import PyPDF2
except ImportError:
    print("错误：未安装PyPDF2，请执行 pip install PyPDF2==2.12.1")
    sys.exit(1)

try:
    import pdfplumber
except ImportError:
    print("错误：未安装pdfplumber，请执行 pip install pdfplumber==0.10.2")
    sys.exit(1)

class PDFSplitterEnhanced:
    def __init__(self, input_pdf, output_dir, offset=1):
        self.input_pdf = Path(input_pdf).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.offset = offset
        if not self.input_pdf.exists():
            print(f"错误：输入文件 {self.input_pdf} 不存在")
            sys.exit(1)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_pdf_text(self):
        print("开始提取PDF文本...")
        all_text = []
        with pdfplumber.open(str(self.input_pdf)) as pdf:
            total_pages = len(pdf.pages)
            for i, page in enumerate(pdf.pages, 1):
                progress = int(i / total_pages * 100)
                print(f"提取文本进度：{progress}%（第{i}/{total_pages}页）")
                text = page.extract_text() or ""
                all_text.append(text)
        return all_text

    def find_toc_pages(self, all_text):
        print("\n开始识别目录页...")
        toc_pages = []
        toc_lines = []
        max_search = min(10, len(all_text))
        for i in range(max_search):
            text = all_text[i] or ""
            lines = text.split('\n')
            toc_like_count = sum(
                bool(re.search(r'[\.．…·]{2,}\s*\d{1,4}$', line.strip())) for line in lines
            )
            if toc_like_count >= 3:  # 目录页
                toc_pages.append(i+1)
                toc_lines.append(text)
                print(f"识别到疑似目录页：第{i+1}页（条目数：{toc_like_count}）\n内容预览：\n{text[:300]}\n-----")
            else:
                print(f"第{i+1}页内容（目录结构行数:{toc_like_count}）:\n{text[:300]}\n-----")
        toc_content = '\n'.join(toc_lines)
        print("\n目录页识别结果（页码）:", toc_pages)
        print("\n目录内容预览:\n", toc_content[:2000], '...' if len(toc_content) > 2000 else '')
        return toc_pages, toc_content

    def parse_toc(self, toc_content):
        print("\n开始解析目录结构...")
        pattern = r'([^\n\d]+?)[\.．…·]{2,}\s*(\d{1,4})$'
        matches = []
        for line in toc_content.split('\n'):
            m = re.search(pattern, line.strip())
            if m:
                title = m.group(1).strip().replace(' ', '').replace('\t','')
                page = int(m.group(2))
                if len(title) >= 2 and not title.isdigit():
                    matches.append((title, page))
        if not matches:
            print("警告：未解析到任何章节。原目录内容片段如下：")
            print(toc_content[:2000], '...' if len(toc_content) > 2000 else '')
            return None

        # 打印所有章节，全量无省略
        print("\n目录章节解析结果（章节名:目录页码）:")
        for index, (k, v) in enumerate(matches, 1):
            print(f"{index}. {k}: 第{v}页")
        chapter_pages = {t: p for t,p in matches}
        return chapter_pages

    def generate_split_plan(self, chapter_pages, total_pages):
        print("\n生成拆分计划...")
        chapters = list(chapter_pages.items())
        split_plan = []
        for i, (chapter, toc_page) in enumerate(chapters):
            start_page = toc_page + self.offset - 1
            # 修正：最后一章的 end_page 不得超出 total_pages
            if i < len(chapters) - 1:
                end_page = chapters[i+1][1] + self.offset - 2
            else:
                end_page = total_pages - 1  # 最后一章到最后一页（页码0开始）
            split_plan.append({
                "chapter": chapter,
                "start": start_page,
                "end": end_page
            })
            print(f"{i+1}: {chapter} → 页码范围：{start_page+1}-{end_page+1}（PDF实际页码）")
        print("\n完整拆分计划：")
        for i, plan in enumerate(split_plan, 1):
            print(f"{i}. {plan['chapter']}: 页码={plan['start']+1}-{plan['end']+1}")
        return split_plan

    def split_pdf(self, split_plan, total_pages):
        print("\n开始拆分PDF...")
        with open(self.input_pdf, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for i, plan in enumerate(split_plan, 1):
                chapter = plan["chapter"]
                start = plan["start"]
                end = plan["end"]
                # 修正：最后一章允许到 total_pages-1
                if start < 0 or end >= total_pages or start > end:
                    print(f"警告：章节【{chapter}】页码范围无效，跳过（start:{start+1}, end:{end+1}, pdf total:{total_pages})")
                    continue
                safe_chapter_name = re.sub(r'[\\/:*?"<>|\n ]', "_", chapter)[:32]
                output_path = self.output_dir / f"{i:02d}_{safe_chapter_name}.pdf"
                pdf_writer = PyPDF2.PdfWriter()
                for page_num in range(start, end+1):
                    pdf_writer.add_page(pdf_reader.pages[page_num])
                with open(output_path, "wb") as out_f:
                    pdf_writer.write(out_f)
                progress = int(i / len(split_plan) * 100)
                print(f"拆分进度：{progress}% → 已保存：{output_path}")
        print(f"\n✅ PDF拆分完成！所有文件已保存至：{self.output_dir}")

    def run(self):
        all_text = self.extract_pdf_text()
        toc_pages, toc_content = self.find_toc_pages(all_text)
        chapter_pages = self.parse_toc(toc_content)
        if not chapter_pages:
            sys.exit(1)
        with pdfplumber.open(str(self.input_pdf)) as pdf:
            total_pages = len(pdf.pages)
        split_plan = self.generate_split_plan(chapter_pages, total_pages)
        self.split_pdf(split_plan, total_pages)

def main():
    parser = argparse.ArgumentParser(description="强化目录识别和章节拆分（Python 3.8，支持 offset 对齐）")
    parser.add_argument("-i", "--input", required=True, help="输入PDF文件路径")
    parser.add_argument("-o", "--output", required=True, help="输出目录路径")
    parser.add_argument("--offset", type=int, default=1, help="目录页码与pdf页码对齐差（正文第一页的pdf页码，即目录中的第1页对应pdf的哪一页？）")
    args = parser.parse_args()
    splitter = PDFSplitterEnhanced(args.input, args.output, args.offset)
    splitter.run()

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
    except Exception:
        pass
    main()
