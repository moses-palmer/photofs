#!/usr/bin/env python
# coding: utf-8
# photofs
# Copyright (C) 2012-2014 Moses Palmér
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.


def make_unique(mapping, base_name, format_1, format_n, *args):
    """Creates a unique key in a ``dict``.

    First the string ``format_1 % base_name`` is tried. If that is present in
    ``mapping``, the strings ``format_n % ((base_name, n) + args)`` with ``n``
    incrementing from ``2`` are tried until a unique one is found.

    :param str base_name: The name of the file without extension.

    :param str format_1: The initial format string. This will be passed
        ``base_name`` followed by ``args``.

    :param str format_n: The fallback format string. This will be passed
        ``base_name`` followed by an index and then ``args``.

    :param args: Format string arguments used.

    :return: a unique key
    :rtype: str
    """
    i = 1
    key = format_1 % ((base_name,) + args)
    while key in mapping:
        i += 1
        key = format_n % ((base_name, i) + args)

    return key
