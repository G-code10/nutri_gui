import sys
sys.path.append("..")

import nutriscore_ean

code_list = []

code_list.append(("18431847", False))
code_list.append(("0899703688022", False))
code_list.append(("0099990004067", False))
code_list.append(("586131209420001392", False))
code_list.append(("10826846237078", False))
code_list.append(("703801607220001872", False))
code_list.append(("10550364", False))
code_list.append(("0405648943681", False))
code_list.append(("336895640495000", False))
code_list.append(("11354135", False))
code_list.append(("8096637211132500009995", False))
code_list.append(("190371010001043371", False))
code_list.append(("13251212512000012473", False))
code_list.append(("548015600521003086", False))
code_list.append(("558052745708262", False))
code_list.append(("325622868654100", False))
code_list.append(("52444534496473085272", False))
code_list.append(("230582790010003500003509", False))
code_list.append(("00179726", False))
code_list.append(("0", False))
code_list.append(("000000", False))
code_list.append(("aqwzsxed", False))
code_list.append(("aqwzsxedcrfvt", False))

code_list.append(("5711812902615", True))
code_list.append(("8713958045505", True))
code_list.append(("8690558039595", True))
code_list.append(("0078742028316", True))
code_list.append(("7702045625806", True))
code_list.append(("4015533032448", True))
code_list.append(("5060420338256", True))
code_list.append(("0038000114243", True))
code_list.append(("3396410253776", True))
code_list.append(("8058333250465", True))
code_list.append(("8410909150010", True))
code_list.append(("8567596030665", True))
code_list.append(("7290019205272", True))
code_list.append(("8904089325806", True))
code_list.append(("4260685420364", True))
code_list.append(("4000462810076", True))
code_list.append(("0050428371060", True))
code_list.append(("4100060018666", True))
code_list.append(("5099556026065", True))
code_list.append(("0004690643301", True))

error_found = 0
for code in code_list:
    if nutriscore_ean.EAN(code[0]).check() != code[1]:
        print(f"ERROR: {code[0]}")
        error_found = error_found + 1
    # else:
    #     print(f"SUCESS: {code[0]}")

print(f"{error_found} erreur(s) trouvée(s)")
