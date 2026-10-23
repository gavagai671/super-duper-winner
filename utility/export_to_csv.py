from utility.calculator import Calculator, CalculatorSettings


if __name__ == '__main__':
    options = CalculatorSettings()
    o = Calculator(options)
    o.export_to_csv()
