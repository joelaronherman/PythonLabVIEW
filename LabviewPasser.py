# -------------- LabviewPasser 1.0 --------------
#
#        Joel Herman         July 11, 2018
# 
# This script allows for the easy integration of
# python into labview, with no loss of precision
# and no need to convert arguments to strings.
# All numeric types are converted to python's
# closest equivalent (either a numpy type, list,
# str, or numpy.ndarray), or a variant object.
# 
# NOTE: This script is designed to work with PythonWrapper.vi version 1.0
# Check VI version 
# 
# Pass arguments as a variant of a cluster of args
# 
# MAKE THE FOLLOWING SUBSTITUTION IN YOUR PYTHON
# CODE to replace b10 command line arguments w/
# a single Labview flattened variant argument:
# argv -> LabviewVariantParser.readFromLabView(argv[1])
#
# List of unsupported Labview data types:
# 	all extended-precision (80-bit) types
# 		extended-precision double
# 		extended-precision complex
# 		extended-precision physical quantity
# 		extended-precision complex physical quantity
# 	time stamp
# 	picture
# 	waveform
# 	refnum
# 	
# To learn more about labview data types and how
# they are encoded by variant->flattenToString, visit
# -> http://zone.ni.com/reference/en-XX/help/371361R-01/lvconcepts/type_descriptors/
#   and
# -> http://zone.ni.com/reference/en-XX/help/371361P-01/lvconcepts/flattened_data/

import sys
from os import devnull
from ctypes import *
import numpy as np
import struct
from collections import deque
from binascii import hexlify

labviewVersion = 16
suppressPrinting = True 	# Only turn to False if running print tests. MUST be
							# TRUE for code to work

############################# VARIANT CLASS ##############################
##########################################################################
class variant:					# This class MUST be used every time a
	def __init__(self, data):	# variant type would be used in LabVIEW.
		self.data = data		# It is a simple wrapper for any datatype.
	def dtype(self):
		return self.data.__class__.__name__
	def __str__(self):
		return "<Variant: " + str(self.data) + ">"

###################### TYPENOTSUPPORTED EXCEPTION ########################
##########################################################################
class TypeNotSupportedException(Exception):
	def __init__(self, message):
		super(TypeNotSupportedException, self).__init__(message)

######################################## GETFROMLABVIEW() ########################################
##################################################################################################
# This method is used to pass data from LabVIEW to Python. It collects the flattend LabVIEW
# data structure from sys.argv[1] and returns the equivalent data structure in Python.
def getFromLabview():
	# if len(sys.argv) <= 1:	# If there is no argument (aka not called by LabVIEW), return 'None'
	# 	return None			# and do not disable printing. This allows for user diagnostics.

	if suppressPrinting:
		sys.stdout = open(devnull, 'w')	# Disable printing until last line of 'sendToLabview()'. Any
										# unexpected print statements will interfere data passing.

	########################### 'GLOBAL' CONSTANTS ###########################
	##########################################################################
	# data = deque(bytearray.fromhex(sys.argv[1]))	# the data to be unflattened
	data = deque(bytearray.fromhex(sys.argv[1]))
				#	'data' acts as a global variable throughout unflattening.

	methodLookup = {	# converts typecodes to a type-specific parser to call
		0x00	:	"parseNone",
		0x01	:	"parseInt8",
		0x02	:	"parseInt16",
		0x03	:	"parseInt32",
		0x04	:	"parseInt64",
		0x05	:	"parseUInt8",
		0x06	:	"parseUInt16",
		0x07	:	"parseUInt32",
		0x08	:	"parseUInt64",
		0x09	:	"parseFloat32",
		0x0A	:	"parseFloat64",
		0x0C	:	"parseComplex64",
		0x0D	:	"parseComplex128",
		0x15	:	"parseInt8",
		0x16	:	"parseInt16",
		0x17	:	"parseInt32",
		0x19	:	"parseFloat32",
		0x1A	:	"parseFloat64",
		0x1C	:	"parseComplex64",
		0x1D	:	"parseComplex128",
		0x21	:	"parseBool",
		0x30	:	"parseStr",
		0x32	:	"parsePath",
		0x40	: 	"parseArray",
		0x50	: 	"parseCluster",
		0x53	:	"parseVariant"
	}

	######################## 'GLOBAL' UTILITY METHODS ########################
	##########################################################################
	def bytesToInt(b):
		i = 0
		for e in b:
			i = (i<<8) + e
		return i

	def mPeek(n=1):
		return bytearray(map(lambda x: data[x], range(n)))

	def mPop(n=1):
		return bytearray(map(lambda x: data.popleft(), range(n)))

	def nPeek(n=1):
		return bytesToInt(mPeek(n))

	def nPop(n=1):
		return bytesToInt(mPop(n))

	############################# VARIANT PARSER #############################
	##########################################################################
	def variantParser():	# As all passed data is contained within a variant,
							# all other type-specific parsers are contained within.

		descriptors = []	# List of type descriptors
							# Includes all types found inside this variant

		######################### TYPE-SPECIFIC PARSERS ##########################
		##########################################################################
		def parseNone(__):
			return None

		def parseInt8(__):
			return np.int8(c_char(nPop()))

		def parseInt16(__):
			return np.int16(c_short(nPop(2)))

		def parseInt32(__):
			return np.int32(c_long(nPop(4)))

		def parseInt64(__):
			return np.int64(c_longlong(nPop(8)))

		def parseUInt8(__):
			return np.uint8(c_uchar(nPop()))

		def parseUInt16(__):
			return np.uint16(c_ushort(nPop(2)))

		def parseUInt32(__):
			return np.uint32(c_uint32(nPop(4)))

		def parseUInt64(__):
			return np.uint64(c_ulonglong(nPop(8)))

		def parseFloat32(__):
			return np.float32(cast(pointer(c_int32(nPop(4))), POINTER(c_float)).contents)

		def parseFloat64(__):
			return np.float64(cast(pointer(c_longlong(nPop(8))), POINTER(c_double)).contents)

		def parseComplex64(__):
			return np.complex64(parseFloat32(__) + parseFloat32(__)*1j)

		def parseComplex128(__):
			return np.complex128(parseFloat64(__) + parseFloat64(__)*1j)

		def parseBool(__):
			return bool(nPop())

		def parseStr(__):
			return str(mPop(nPop(4)).decode())

		def parsePath(index):
			mPop(4)
			l = nPop(4)
			mPop(4)
			d = chr(mPop(3)[1])
			p = mPop(l-7)
			dot = False
			for i in range(len(p)):
				if (p[i]>>4) < 2:
					p[i] = 0x5C
			if not 0x2E in p:
				p.append(0x5C)
			return d + ':\\' + ''.join(map(chr, p))

		def parseArray(index):
			descriptor = descriptors[index]
			n = bytesToInt(descriptor[4:6])		# number of dimensions
			dims = tuple(map(lambda x: nPop(4), range(n)))
			elementD = bytesToInt(descriptor[-2:])
			if bytesToInt((descriptors[elementD])[3:4]) == 0x50:# if array of type 'cluster': Special Case
				a = np.empty(dims, dtype=object)				# case stops numpy from automatically
				for c, __ in np.ndenumerate(a):					# casting interior lists to numpy.arrays
					a[c] = parseCluster(elementD)				# by explicitly stating dtype=object
				return a
			return np.array(np.reshape(list(map(lambda __: parser(elementD), range(np.prod(dims)))), dims))

		def parseCluster(index):
			descriptor = descriptors[index]
			return list(map(lambda x: parser(bytesToInt(descriptor[6+2*x:8+2*x])), range(bytesToInt(descriptor[4:6]))))

		def parseVariant(__):		# wrapper method to recursively call 'variantParser'. Useful in that
			return variantParser()	# it appears on same level of heirarchy as other type-specific parsers

		def raiseException(index):
			raise TypeNotSupportedException("Labview type 0x" + (descriptors[index])[3:4].hex().upper() + " is not supported by this version of LabViewPasser.")

		############################ GENERIC PARSER ##############################
		##########################################################################
		variantLocals = locals()	# captures 'locals()' in the parseVariant scope, for use in
									# evaluating strings into type-specific parser method names.
		def parser(index):
			return eval(methodLookup.get(bytesToInt((descriptors[index])[3:4]), "raiseException"), variantLocals)(index)	# calls appropriate type-specific parser
		
		# - - - - - - - - - continuation of 'variantParser()' - - - - - - - - -  #
		mPop(4)
		descriptors = tuple(map(lambda __: mPop(nPeek(2)), range(nPop(4))))	# determines the number of types, then pops each
		mPop(2)																# type into  descriptors, according to its length.
		temp = parser(nPop(2))
		mPop(4)
		return variant(temp)

	return variantParser().data


################################### SENDTOLABVIEW(dataToSend) ####################################
##################################################################################################
# This method passes data from Python to LabVIEW. It wraps the Python data from 'dataToSend'
# in a variant and encodes it in LabVIEW's flattened string data format. The result is printed.
def sendToLabview(dataToSend):
	if dataToSend is None and len(sys.argv) <= 1:
		return

	methodLookup = {	# converts typecodes to a specific exporter to call
		"NoneType"		:	"exportNone",
		"int8"			:	"exportInt8",
		"int16"			:	"exportInt16",
		"int32"			:	"exportInt32",
		"int64"			:	"exportInt64",
		"uint8"			:	"exportUInt8",
		"uint16"		:	"exportUInt16",
		"uint32"		:	"exportUInt32",
		"uint64"		:	"exportUInt64",
		"float32"		:	"exportFloat32",
		"float64"		:	"exportFloat64",
		"complex64"		:	"exportComplex64",
		"complex128"	:	"exportComplex128",
		"bool_"			:	"exportBoolean",
		"bool"			:	"exportBoolean",
		"int"			:	"exportInt32",
		"float"			:	"exportFloat64",
		"complex"		:	"exportComplex128",
		"str"			:	"exportString",
		"ndarray"		:	"exportArray",
		"list"			:	"exportCluster",
		"object"		:	"exportVariant",
		"variant"		:	"exportVariant"
	}

	############################ VARIANT EXPORTER ############################
	##########################################################################
	def variantExporter(v):	# As all passed data is enclosed inside a variant,
							# all other type-specific exporters are contained within.

		descriptors = []	# List of type descriptors
							# Includes all types found inside this variant

		######################## TYPE-SPECIFIC EXPORTERS #########################
		##########################################################################
		def exportNone(__, suppressDescriptors=False):
			return None if suppressDescriptors else "00040000", ""

		def exportInt8(num=0, suppressDescriptors=False):
			return None if suppressDescriptors else "0005000100", hex(struct.unpack("=B", struct.pack("=b", num))[0])[2:].zfill(2)

		def exportInt16(num=0, suppressDescriptors=False):
			return (None if suppressDescriptors else "0005000200"), hex(struct.unpack("=H", struct.pack("=h", num))[0])[2:].zfill(4)

		def exportInt32(num=0, suppressDescriptors=False):
			return None if suppressDescriptors else "0005000300", hex(struct.unpack("=L", struct.pack("=l", num))[0])[2:].zfill(8)

		def exportInt64(num=0, suppressDescriptors=False):
			return None if suppressDescriptors else "0005000400", hex(struct.unpack("=Q", struct.pack("=q", num))[0])[2:].zfill(16)

		def exportUInt8(num=0, suppressDescriptors=False):
			return None if suppressDescriptors else "0005000500", hex(num)[2:].zfill(2)

		def exportUInt16(num=0, suppressDescriptors=False):
			return None if suppressDescriptors else "0005000600", hex(num)[2:].zfill(4)

		def exportUInt32(num=0, suppressDescriptors=False):
			return None if suppressDescriptors else "0005000700", hex(num)[2:].zfill(8)

		def exportUInt64(num=0, suppressDescriptors=False):
			return None if suppressDescriptors else "0005000800", hex(num)[2:].zfill(16)

		def exportFloat32(num=0.0, suppressDescriptors=False):
			return None if suppressDescriptors else "0005000900", hex(struct.unpack("=L", struct.pack("=f", num))[0])[2:].zfill(8)

		def exportFloat64(num=0.0, suppressDescriptors=False):
			return None if suppressDescriptors else "0005000a00", hex(struct.unpack("=Q", struct.pack("=d", num))[0])[2:].zfill(16)

		def exportComplex64(num=0.0, suppressDescriptors=False):
			return None if suppressDescriptors else "0005000c00", hex(struct.unpack("=Q", struct.pack("=ff", num.imag, num.real))[0])[2:].zfill(16)

		def exportComplex128(num=0.0, suppressDescriptors=False):
			s = struct.unpack("=QQ", struct.pack("=dd", num.real, num.imag))
			return None if suppressDescriptors else "0005000d00", hex(s[0])[2:].zfill(16) + hex(s[1])[2:].zfill(16)
			
		def exportBoolean(b=False, suppressDescriptors=False):
			return None if suppressDescriptors else "00040021", hex(struct.unpack("=B", struct.pack("=?", b))[0])[2:].zfill(2)

		def exportString(s='', suppressDescriptors=False):
			return None if suppressDescriptors else "00080030ffffffff", exportInt32(len(s))[1] + hexlify(bytearray(s, 'ascii')).decode()

		def exportArray(a=np.empty((0,), dtype=np.float64), suppressDescriptors=False):
			dims = a.shape
			n = len(dims)
			flat = a.flat	# returns an iterator that iterates over a 1-dimensional version of 'a'
			dimData = ''.join(list(map(lambda i: exportInt32(dims[i], True)[1], range(len(dims)))))	# converts 'dims' to a string
			if a.size > 0:
				elementD, data0 = export((flat[0]), suppressDescriptors)	# collects type-descriptor from first element, while simultaneously populating the first spot in the flattend data.
				return None if suppressDescriptors else exportUInt16(8+4*n, True)[1] + '0040' + exportUInt16(n, True)[1] + 'f'*8*n + elementD, dimData + data0 + ''.join(list(map(lambda e: export(e, True)[1], flat[1:])))
			return None if suppressDescriptors else exportUInt16(8+4*n, True)[1] + '0040' + exportUInt16(n, True)[1] + 'f'*8*n + export(dtype=a.dtype)[0], dimData # uses 'a.dtype' to get type descriptor if 'a' is empty

		def exportCluster(c=[], suppressDescriptors=False):
			temp = list(zip(*list(map(lambda e: list(export(e, suppressDescriptors)), c))))
			return None if suppressDescriptors else exportUInt16(6+2*len(c), True)[1] + '0050' + exportUInt16(len(c), True)[1] + ''.join(temp[0]), ''.join(temp[1])

		def exportVariant(v=None, suppressDescriptors=False):					# wrapper method to recursively call 'variantExporter'. Useful in that it appears
			return None if suppressDescriptors else "00040053", variantExporter(v) if v else None	# on same level of heirarchy as other type-specific exporters

		def raiseException(data, __):
			raise TypeNotSupportedException("Python type " + str(data.__class__.__name__) + " is not supported by LabVIEW. (see VI help file for list of supported types)")

		########################### GENERIC EXPORTER #############################
		##########################################################################
		variantLocals = locals()	# captures 'locals()' in the parseVariant scope, for use in
									# evaluating strings into type-specific exporter method names.
		def export(data=None, suppressDescriptors=False, dtype=None):
			descriptor, hexData = '', ''
			if dtype is None:
				descriptor, hexData = eval(methodLookup.get(data.__class__.__name__, "raiseException"), variantLocals)(data, suppressDescriptors)	
			else:																												# calls appropriate type-specific exproter
				descriptor, hexData = eval(methodLookup.get(str(dtype), "raiseException"), variantLocals)(suppressDescriptors=suppressDescriptors)

			if not suppressDescriptors:
				dNum = 0
				try:										# Finds type descriptor in list of
					dNum = descriptors.index(descriptor)	# descriptors, and returns its index.
				except ValueError:							# If not found, adds type descriptor
					descriptors.append(descriptor)			# to the end of the list, and returns
					dNum = len(descriptors)-1				# the final index of the list.
				descriptor = exportUInt16(dNum, True)[1]
			return descriptor, hexData

		#  - - - - - - - - continuation of 'variantExporter(v)' - - - - - - - -  #
		descriptor, hexData = export(v.data)
		return str(labviewVersion*100) + "8000" + exportUInt32(len(descriptors))[1] + ''.join(descriptors) + "0001" + descriptor + hexData + "00000000"

	sys.stdout = sys.__stdout__	# re-enable printing
	sys.stdout.write(variantExporter(variant(dataToSend)) + "\n")
