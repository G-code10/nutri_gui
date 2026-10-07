import cv2
import zxingcpp

## @package CodeBarReader
# @brief Tentative de récupéretion de code bar
# @details Ce module permet la lecture d'image sous différente source, fichier, caméra (TODO) pour y détecter et retourner un ou plusieurs code bar

class CodeBarReader:
      """! class de traitement d'une image pour y détecter et y trouver son code bar"""

      def __init__(self, debug : bool = False):
            """! Constructeur CodeBarReader"""
            self.__debug = debug

      def from_image(self, image_path : str):
            try:
                  img = cv2.imread(image_path)
            except:
                  return None
            
            barcodes = zxingcpp.read_barcodes(img, try_rotate=True, try_downscale=True)
            if not barcodes:
                  return None
            
            return barcodes

      def __str__(self):
            return "CodeBarReader class"
