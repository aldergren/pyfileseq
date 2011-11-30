#!/usr/bin/env python

"""
PyFileSeq, a library for working with file sequences on disk.

Author: Niklas Aldergren <niklas@aldergren.com>

This is probably most useful when working with applications that
generate a lot of sequential images, e.g. scanning, rendering, etc. It
should (hopefully) support any imaginable file sequence out there and
be reasonably fast.

In ambiguous cases (such as files 999, 0999 & 1000 being present) the finder
methods will prefer padded sequences over unpadded.

Usage:

>>> from fileseq import FileSequence
>>> sequences, others = FileSequence.find('/stuff')
>>> sequences[0]
my_sequence.[0001-0005].ext

>>> my_sequence = sequences[0]
>>> for filename in my_sequence:
...     print filename
... 
my_sequence.0001.ext
my_sequence.0002.ext
my_sequence.0003.ext
my_sequence.0004.ext
my_sequence.0005.ext

>>> my_sequence.format("{head}{padchars}{tail}")
'my_sequence.####.ext'

"""

__author__ = "Niklas Aldergren <niklas@aldergren.com>"
__version__ = "1.0.0"

import re
import os

class FileSequence():
    """
    A sequence of files. In most ways, a FileSequence can be treated as a list; 
    it has a length, supports slicing and will yield all filenames if enumerated.

    Attributes:

    head: Any part of the filename preceding the counter.
    tail: Any part of the filename following the counter.
    first: First number in sequence.
    last: Last number in sequence.
    padding: Number of padding digits used.
    path: Path to the sequence.
    name: Any part of the filename preceding the counter, excluding common delimiters.
    extension: Filename extension, excluding any delimiter.
    """

    NUMBER_PATTERN = re.compile("([0-9]+)")

    def __init__(self, path = "", head = "", tail = "", first = 0, last = 0, padding = 0):
        self.path = ""
        self.head = head
        self.tail = tail
        self.first = first
        self.last = last
        self.padding = padding

    def __len__(self):
        return (self.last - self.first) + 1

    def __repr__(self):
        return "".join([self.head,
                        "[",
                        str(self.first).zfill(self.padding), 
                        "-", 
                        str(self.last).zfill(self.padding),
                        "]",
                        self.tail])

    def __iter__(self):
        def filesequence_iter_generator():
            for n in range(self.first, self.last + 1):
                yield self.filename(n)
        return filesequence_iter_generator()

    def __getitem__(self, key):
        if isinstance(key, slice):
            return [self.__getitem__(i)
                    for i in xrange(*key.indices(len(self)))]
        else:
            if isinstance(key, int):
                if key >= 0:
                    return self.filename(self.first + key)
                else:
                    return self.filename(self.last - (key * -1) + 1)
            else:
                raise TypeError, "sequence indexes must be integers"
            
    def filename(self, number):
        """Return the filename for the given absolute number in the sequence."""
        if number >= self.first and number <= self.last:
            return "".join([self.head,
                           str(number).zfill(self.padding),
                           self.tail])
        else:
            raise IndexError, "number out of sequence range"

    def format(self, template="{head}%0{padding}d{tail}", padchar="#"):
        """Return the file sequence as a formatted string according to
        the given template. Due to the use of format(), this method requires
        Python 2.6 or later.

        The template supports all the basic sequence attributes, i.e.
        head, tail, first, last, length, padding, path. 

        In addition, it supports the following:

        padchars - character repeated to match padding (at least one)
        range - sequence range as a string, first-last
        """

        values = {"head": self.head,
                  "tail": self.tail,
                  "first": self.first,
                  "last": self.last,
                  "length": len(self),
                  "padding": self.padding,
                  "padchars": padchar * self.padding or padchar,
                  "range": "-".join([str(self.first), str(self.last)]),
                  "path": self.path}

        return template.format(**values)

    @property
    def name(self):
        return self.head.rstrip('.')

    @property
    def extension(self):
        return self.tail.split('.')[-1]

    @classmethod
    def find(cls, search_path):
        """
        Find all file sequences at the given path. Returns a tuple (sequences, other_files).
        """
        sequences, other_files = cls.find_in_list(os.listdir(search_path))
        for sequence in sequences:
            sequence.path = search_path
        return sequences, other_files

    @classmethod
    def find_in_list(cls, entries):
        """
        Find all file sequences in a list of files. Returns a tuple (sequences, other_files).
        """
        sequences = []
        other_files = []

        # We sort the list to ensure that padded entries are found before any
        # unpadded equivalent.

        entries.sort()

        # Our strategy here is to pop a filename off the list, and search the
        # remaining entries for adjacent files that would indicate it is part of
        # a file sequence.

        while entries:

            entry = entries.pop(0)
            sequence = None

            def adjacent_files(components, index, padding, reverse=False):
                adj_components = components[:]
                number = int(components[index])

                if reverse:
                    for n in xrange(number - 1, 0, -1):
                        adj_components[index] = str(n).zfill(padding)
                        yield ''.join(adj_components), n
                else:
                    for n in xrange(number + 1, number + len(entries) + 1):
                        adj_components[index] = str(n).zfill(padding)
                        yield ''.join(adj_components), n

            # There is no reliable way to determine what the correct numeric portion
            # is of a single filename.

            components = cls.NUMBER_PATTERN.split(entry)

            # For each numeric component in the filename, we try that as the counter field.
            # The last numeric portion is usually the correct one, so we check backwards.

            for i in range(len(components) - 2, 0, -2):

                first = int(components[i])
                last = int(components[i])

                # Since the list is sorted, we know 0999 will always appear before 1000
                # so this should be safe.

                if components[i].startswith("0"):
                    padding = len(components[i])
                else:
                    padding = 0

                # First, we attempt to find the upper bound of this sequence..
                for filename, number in adjacent_files(components, i, padding):
                    if filename in entries:
                        entries.remove(filename)
                        last = number
                    else:
                        break

                # ..and then the lower bound.
                for filename, number in adjacent_files(components, i, padding, reverse=True):
                    if filename in entries:
                        entries.remove(filename)
                        first = number
                    else:
                        break

                if (first - last):
                    # We've found what looks like a sequence of files.
                    sequence = FileSequence("",
                                            "".join(components[:i]), 
                                            "".join(components[i + 1:]),
                                            first,
                                            last,
                                            padding)
                    break
                else:
                    pass

            if sequence:
                sequences.append(sequence)
            else:
                # This file is not part of any sequence.
                other_files.append(entry)

        return sequences, other_files


if __name__ == "__main__":
    import sys
    sequences, others = FileSequence.find(sys.argv[1])
    for s in sequences:
        print s

