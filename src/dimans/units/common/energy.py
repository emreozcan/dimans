from fractions import Fraction as _Fraction

from ..si_derived.joule import joule as _joule

british_thermal_unit = (1_055 * _joule).as_derived_unit("BTU")
erg = (_Fraction(1, 10**7) * _joule).as_derived_unit("erg")
