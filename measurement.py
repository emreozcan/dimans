from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from fractions import Fraction
from numbers import Number, Rational
from typing import Any

import attrs


@attrs.define(slots=True, frozen=True, eq=False)
class Quantity:
    value: Number
    unit: CompoundUnit


@attrs.define(slots=True, frozen=True, repr=False)
class CompoundUnit:
    """Represents a product of one or more base units."""
    symbol: str | None
    unit_exponents: Mapping[BaseUnit, Fraction | float]

    @classmethod
    def named(
        cls,
        symbol: str,
        exponents_or_unit: Mapping[BaseUnit, Fraction | float] | CompoundUnit,
        /
    ):
        if isinstance(exponents_or_unit, CompoundUnit):
            return cls(symbol, exponents_or_unit.unit_exponents)
        return cls(symbol, exponents_or_unit)

    def __str__(self):
        if self.symbol:
            return self.symbol
        return self._str_with_multiplicands()

    def __repr__(self):
        if self.symbol:
            return (f"<{self.__class__.__name__} {self} "
                    f"= {self._str_with_multiplicands()}>")
        return f"<{self.__class__.__name__} {self}>"

    def __pow__(self, power: int | Fraction | float, modulo=None):
        if not isinstance(power, float):
            if not isinstance(power, Rational):
                return NotImplemented
            power = Fraction(power)
        return CompoundUnit(None, {
            base_unit: exponent * power
            for base_unit, exponent in self.unit_exponents.items()
        })

    def __mul__(self, other: Any, /):
        if isinstance(other, CompoundUnit):
            base_units = []
            for unit in self.unit_exponents.keys():
                if unit not in base_units:
                    base_units.append(unit)
            for unit in other.unit_exponents.keys():
                if unit not in base_units:
                    base_units.append(unit)

            return CompoundUnit(None, {
                base_unit: exponent
                for base_unit, exponent in {
                    base_unit:
                        self.unit_exponents.get(base_unit, 0) +
                        other.unit_exponents.get(base_unit, 0)
                    for base_unit in base_units
                }.items()
                if exponent != 0
            })

        if isinstance(other, Number):
            return Quantity(other, self)
        return NotImplemented

    def __rmul__(self, other):
        return self * other  # Multiplication is commutative

    def __truediv__(self, other: Any, /):
        if other == 1:
            return self
        if isinstance(other, CompoundUnit):
            return self * other.multiplicative_inverse()
        return NotImplemented

    def __rtruediv__(self, other: Any, /):
        if other == 1:
            return self.multiplicative_inverse()
        return other * self.multiplicative_inverse()

    def _str_with_multiplicands(self):
        if not self.unit_exponents:
            return "1"
        return " ".join([
            f"{base_unit}^{exponent}" if exponent != 1 else str(base_unit)
            for base_unit, exponent in self.unit_exponents.items()
        ])

    def multiplicative_inverse(self):
        return CompoundUnit(None, {
            base_unit: -exponent
            for base_unit, exponent in self.unit_exponents.items()
        })

    def dim(self):
        dimensions = {}
        for base_unit, exponent in self.unit_exponents.items():
            if base_unit.dimension not in dimensions:
                dimensions[base_unit.dimension] = exponent
            else:
                dimensions[base_unit.dimension] += exponent
                if dimensions[base_unit.dimension] == 0:
                    del dimensions[base_unit.dimension]
        return Dimensions.from_map(dimensions)

    def si_factor(self):
        factor = 1
        for base_unit, exponent in self.unit_exponents.items():
            factor *= base_unit.si_factor ** exponent
        return factor

    def conversion_factor_to(self, other: CompoundUnit | BaseUnit, /):
        """Get the conversion factor from this unit to another unit.

        This method returns the factor
        by which a measurement in this unit must be multiplied
        to get a measurement in the other unit.
        """
        if isinstance(other, BaseUnit):
            other = other.as_unit()
        if self.dim() != other.dim():
            raise ValueError(f"units must have the same dimensions")
        return self.si_factor() / other.si_factor()

    def conversion_factor_from(self, other: CompoundUnit | BaseUnit, /):
        """Get the conversion factor from another unit to this unit.

        This method returns the factor
        by which a measurement in the other unit must be multiplied
        to get a measurement in this unit.
        """
        if isinstance(other, BaseUnit):
            other = other.as_unit()
        if self.dim() != other.dim():
            raise ValueError(f"units must have the same dimensions")
        return other.si_factor() / self.si_factor()


@attrs.define(slots=True, frozen=True, repr=False)
class BaseUnit:
    """A unit of measurement which only has one dimension of power 1.

    What the above statement means in layman's terms is that
    a base unit is a unit, which is not a combination of other units.

    For example, the meter is a base unit, the second is a base unit, but
    meters per second is not a base unit.
    """

    symbol: str
    """The symbol of the unit.

    This value is used to generate human-readable representations of
    quantities."""

    dimension: Dimension
    """The dimension of the unit."""

    si_factor: Fraction
    """The factor by which the base SI unit of the dimension is multiplied by.
    """

    def __str__(self):
        return self.symbol

    def __repr__(self):
        return f"<{self.__class__.__name__} {self}>"

    def __pow__(self, power: int | Fraction | float, modulo=None):
        if not isinstance(power, float):
            if not isinstance(power, Rational):
                return NotImplemented
            power = Fraction(power)
        return CompoundUnit(None, {self: power})

    def __mul__(self, other: Any, /):
        if isinstance(other, CompoundUnit):
            return self.as_unit() * other

        if isinstance(other, BaseUnit):
            if self == other:
                return self ** 2
            return self.as_unit() * other.as_unit()

        if isinstance(other, Number):
            return Quantity(other, self.as_unit())
        return NotImplemented

    def __rmul__(self, other: Any, /):
        return self * other  # Multiplication is commutative

    def __truediv__(self, other: Any, /):
        if other == 1:
            return self
        if isinstance(other, BaseUnit):
            return self * other.multiplicative_inverse()
        return NotImplemented

    def __rtruediv__(self, other: Any, /):
        if other == 1:
            return self.multiplicative_inverse()
        return other * self.multiplicative_inverse()

    def _check_compatible(self, other: Any, /):
        if not isinstance(other, BaseUnit):
            raise TypeError(f"expected BaseUnit, "
                            f"got {other.__class__.__name__}")
        if self.dimension != other.dimension:
            raise ValueError(f"{self.dimension} unit not compatible with "
                             f"{other.dimension} unit")

    def dim(self):
        return Dimensions.from_map({self.dimension: Fraction(1)})

    def conversion_factor_to(self, other: BaseUnit, /):
        """Get the conversion factor from this unit to another unit.

        This method returns the factor
        by which a measurement in this unit must be multiplied
        to get a measurement in the other unit.
        """
        self._check_compatible(other)
        return self.si_factor / other.si_factor

    def conversion_factor_from(self, other: BaseUnit, /):
        """Get the conversion factor from another unit to this unit.

        This method returns the factor
        by which a measurement in the other unit must be multiplied
        to get a measurement in this unit.
        """
        self._check_compatible(other)
        return other.si_factor / self.si_factor

    def as_unit(self) -> CompoundUnit:
        return CompoundUnit(None, {self: 1})

    def multiplicative_inverse(self) -> CompoundUnit:
        return CompoundUnit(None, {self: -1})


@attrs.define(slots=True, frozen=True, repr=False)
class Dimensions:
    mass: Fraction | float = Fraction(0)
    length: Fraction | float = Fraction(0)
    luminous_intensity: Fraction | float = Fraction(0)
    time: Fraction | float = Fraction(0)
    electric_current: Fraction | float = Fraction(0)
    temperature: Fraction | float = Fraction(0)
    amount_of_substance: Fraction | float = Fraction(0)

    def __str__(self):
        if all(exponent == 0 for exponent in self.as_map().values()):
            return "1"

        return " ".join([
            f"{dimension.value}^{exponent}"
            for dimension, exponent in self.as_map().items()
            if exponent != 0
        ])

    def __repr__(self):
        return f"<{self.__class__.__name__} {self}>"

    @classmethod
    def from_map(cls, _map: Mapping[Dimension, Fraction | float]):
        return cls(
            _map.get(Dimension.MASS, Fraction(0)),
            _map.get(Dimension.LENGTH, Fraction(0)),
            _map.get(Dimension.LUMINOUS_INTENSITY, Fraction(0)),
            _map.get(Dimension.TIME, Fraction(0)),
            _map.get(Dimension.ELECTRIC_CURRENT, Fraction(0)),
            _map.get(Dimension.TEMPERATURE, Fraction(0)),
            _map.get(Dimension.AMOUNT_OF_SUBSTANCE, Fraction(0)),
        )

    def as_map(self) -> Mapping[Dimension, Fraction | float]:
        return {
            Dimension.MASS: self.mass,
            Dimension.LENGTH: self.length,
            Dimension.LUMINOUS_INTENSITY: self.luminous_intensity,
            Dimension.TIME: self.time,
            Dimension.ELECTRIC_CURRENT: self.electric_current,
            Dimension.TEMPERATURE: self.temperature,
            Dimension.AMOUNT_OF_SUBSTANCE: self.amount_of_substance,
        }


class Dimension(Enum):
    MASS = "M"
    LENGTH = "L"
    LUMINOUS_INTENSITY = "J"
    TIME = "T"
    ELECTRIC_CURRENT = "I"
    TEMPERATURE = "Θ"
    AMOUNT_OF_SUBSTANCE = "N"

    def si_base_unit(self) -> BaseUnit | None:
        return si_units[self]


mg = BaseUnit("mg", Dimension.MASS, Fraction(1, 1_000_000))
g = BaseUnit("g", Dimension.MASS, Fraction(1, 1000))
kg = BaseUnit("kg", Dimension.MASS, Fraction(1))
nm = BaseUnit("nm", Dimension.LENGTH, Fraction(1, 1_000_000_000))
um = BaseUnit("µm", Dimension.LENGTH, Fraction(1, 1_000_000))
mm = BaseUnit("mm", Dimension.LENGTH, Fraction(1, 1000))
cm = BaseUnit("cm", Dimension.LENGTH, Fraction(1, 100))
m = BaseUnit("m", Dimension.LENGTH, Fraction(1))
km = BaseUnit("km", Dimension.LENGTH, Fraction(1000))
cd = BaseUnit("cd", Dimension.LUMINOUS_INTENSITY, Fraction(1))
ms = BaseUnit("ms", Dimension.TIME, Fraction(1, 1000))
s = BaseUnit("s", Dimension.TIME, Fraction(1))
h = BaseUnit("h", Dimension.TIME, Fraction(3600))
mA = BaseUnit("mA", Dimension.ELECTRIC_CURRENT, Fraction(1, 1000))
A = BaseUnit("A", Dimension.ELECTRIC_CURRENT, Fraction(1))
K = BaseUnit("K", Dimension.TEMPERATURE, Fraction(1))
mol = BaseUnit("mol", Dimension.AMOUNT_OF_SUBSTANCE, Fraction(1))

lbs = BaseUnit("lbs", Dimension.MASS, Fraction(45359237, 100000000))
oz = BaseUnit("oz", Dimension.MASS, Fraction(45359237, 16*100000000))
inches = BaseUnit("in", Dimension.LENGTH, Fraction(381, 12*1250))
ft = BaseUnit("ft", Dimension.LENGTH, Fraction(381, 1250))
mi = BaseUnit("mi", Dimension.LENGTH, Fraction(201168, 125))

si_units = {
    Dimension.MASS: kg,
    Dimension.LENGTH: m,
    Dimension.LUMINOUS_INTENSITY: cd,
    Dimension.TIME: s,
    Dimension.ELECTRIC_CURRENT: A,
    Dimension.TEMPERATURE: K,
    Dimension.AMOUNT_OF_SUBSTANCE: mol,
}
