import re

## @package NutriscoreSQL
# @brief Connection and query module for postresql server
# @details This module manage the connexion to a postgresql server and the miscaleous queries require for the Nutriscope app

class EAN:
      """! class de validation d'un code bar au format EAN-8 et EAN-13"""

      def __init__(self, code : str, debug : bool = False):
            """! Constructeur EAN"""

            if not isinstance(code, str):
                  raise TypeError("Invalid input parameters format.")
            
            self.__code = code
            self.__debug = debug
            
      def check_format(self):
            if re.match(r"^(\d{8}|\d{13})$", self.__code):
                  return True
            
            if self.__debug:
                  print(f"Le code {self.__code} ne match pas la régle 8/13")
            return False
      
      def get_key(self):
            if not self.check_format():
                  return None

            numbers = [int(x) for x in self.__code]
            head_code = numbers[:-1]
            total = sum(num * (3 if i % 2 == 0 else 1) for i, num in enumerate(reversed(head_code)))

            real_key = numbers[-1]
            key = (10 - (total % 10)) % 10

            if key != real_key:
                  if self.__debug:
                        print(f"Le code {self.__code} à une erreur de clé {key}/{real_key}")
                  return None

            return key

      def check_key(self):
            return self.get_key() != None

      def check(self):
            return self.check_format() and self.check_key()

      def __str__(self):
            return "EAN class"
