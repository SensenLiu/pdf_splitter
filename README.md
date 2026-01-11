# pdf_splitter

python3 pdf_splitter_aug_ai.py  -i 4上中 国古代神话.pdf -o 拆分结果 --toc-pages="5,6,7,8" --first-toc-page=1 --first-phys-page=9 --skip-suffix=0 --use-ocr
参数含义
--toc-pages="5,6,7,8"表示目录所在的pdf的物理页
--first-toc-pag表示目录第一章的脚注页码
 --first-phys-page=9表示第一章第一页对应的物理页
 --skip-suffix=0表示每一章后面需要忽略的页数（用于防止每一张开始前的导读页加入到前一章的末尾）
