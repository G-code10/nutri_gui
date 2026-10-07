import sys
sys.path.append("..")

import nutriscope_code_bar_reader

# une liste d'image dont on connait le code bar...
data_dir = "testU/nutriscope_code_bar_reader_data/"
imgs = ["cb1.jpg", "cb2.jpg", "cb3.jpg", "cb4.jpg", "cb5.jpg", "cb6.jpg", "cb7.jpg", "cb8.jpg", "cb9.jpg", "cb10.jpg"]

codes = [  "4300175167758"
         , "853382004087"
         , "0015891406114"
         , "5292705000064"
         , "829835011001"
         , "1380255610547"
         , "5201219040107"
         , "4311501481608"
         , "076753206280"
         , "050000322909"]

for index, img in enumerate(imgs):
    cbr = nutriscope_code_bar_reader.CodeBarReader()
    barcodes = cbr.from_image(data_dir + img)
    if not barcodes:
        print(f"Impossible de lire le code pour l'image {img}")
    else:
        for barcode in barcodes:
            if barcode.text != codes[index]:
                print(f"Le code pour l'image {index} ne correspond pas {barcode.text} / {codes[index]}")
            break