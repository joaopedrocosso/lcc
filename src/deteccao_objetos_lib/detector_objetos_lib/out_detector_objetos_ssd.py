# Referência:
#	https://www.pyimagesearch.com/2017/09/11/object-detection-with-deep-learning-and-opencv/

import os
import cv2 as cv
import numpy as np

from .detector_objetos_base import BaseDetectorObjetos, DEFAULT_PRECISAO_DETECCAO, DEFAULT_SUPRESSAO_DETECCAO

class DetectorObjetosSSD(BaseDetectorPessoas):

	'''Detecta pessoas usando um modelo SSD.

	Parameters
	-----------
	mobile_ssd_path : str
		Destino do modelo desejado.
	precisao_minima : float, optional
		Quão precisa a detecção deve ser. Deve estar entre 0.0 e 1.0
		incl. (Padrão=Mesmo que o DetectorPessoasBase)
	supressao_caixas : float, optional
		Quão próximas as detecções de pessoas devem estar para
		serem consideradas as mesmas. Deve estar entre 0.0 e 1.0
		incl. (Padrão=Mesmo que o DetectorPessoasBase)

	Raises
	--------
	Exceções relacionadas ao OpenCV.
	'''

	_RESINA_NET_ARQUIVO_MODEL = 'MobileNetSSD_deploy.caffemodel'
	_RESINA_NET_ARQUIVO_PROTOTXT = 'MobileNetSSD_deploy.prototxt'

	def __init__(self, mobile_ssd_path, precisao_minima=DEFAULT_PRECISAO_DETECCAO,
				 supressao_caixas=DEFAULT_SUPRESSAO_DETECCAO):

		super().__init__(precisao_minima, supressao_caixas)

		prototxt = os.path.join(mobile_ssd_path, DetectorObjetosSSD._RESINA_NET_ARQUIVO_PROTOTXT)
		caffemodel = os.path.join(mobile_ssd_path, DetectorObjetosSSD._RESINA_NET_ARQUIVO_MODEL)
		self.net = cv.dnn.readNetFromCaffe(prototxt, caffemodel)

	def detectar(self, img):
		'''Detecta objetos em uma imagem.

		Parameters
		-----------
		img : numpy.ndarray
			Imagem a ser analizada.
		
		Returns
		--------
		caixas_precisoes_rotulos : {'rotulo':([(int, int, int, int), ...], [float, ...]), ...}
			Dicionário de tuplas para cada rótulo. Cada rótulo 
			disponível contém uma array de coordenadas (caixas) dos
			objetos e outra com suas respectivas probabilidades de 
			serem esse objeto.
		'''

		dados_relevantes = self._analisa_imagem(img)
		caixas_precisoes_rotulos = self._seleciona_pessoas(img, dados_relevantes)
		return caixas_precisoes_rotulos

	def _analisa_imagem(self, img):
		'''Analiza uma imagem e retorna dados relevantes

		Parameters
		-----------
		img: numpy.ndarray de dimensões (n, m, 3)
			Imagem a ser analizada. (formato BGR)

		Returns
		--------
		dados_relevantes : numpy.ndarray
			Dados de análise da imagem.
		'''

		blob = cv.dnn.blobFromImage(cv.resize(img, (300, 300)), 2/255.0,
									(300, 300), 127.5)
		self.net.setInput(blob)
		return self.net.forward()

	def _seleciona_pessoas(self, img, dados_relevantes):
		'''Seleciona as pessoas da imagem.
		
		Parameters
		-----------
		img : numpy.ndarray de dimensões (n, m, 3)
			Imagem de onde serão selecionadas as pessoas. (formato BGR)
		dados_relevantes
			Dados relevantes para o selecionamento de pessoas.

		Returns
		--------
		caixas : [(int, int, int, int), ...]
			Caixas que representam pessoas, na forma (x, y, w, h).
		precisoes : [float, ...]
			Precisões de cada caixa.
		'''

		ID_PESSOA = 15
		detections = dados_relevantes

		img_h, img_w = img.shape[:2]

		caixas = []
		precisoes = []

		for i in np.arange(0, detections.shape[2]):
			# extract the confidence (i.e., probability) associated with the
			# prediction
			confidence = detections[0, 0, i, 2]
		 
			# filter out weak detections by ensuring the `confidence` is
			# greater than the minimum confidence
			if confidence >= self.precisao_minima:
				# extract the index of the class label from the `detections`,
				# then compute the (x, y)-coordinates of the bounding box for
				# the object
				idx = int(detections[0, 0, i, 1])
				if idx != ID_PESSOA:
					continue
				box = detections[0, 0, i, 3:7] * np.array([img_w, img_h, img_w, img_h])
				startX, startY, endX, endY = box.astype("int")
				startX, startY, endX, endY = int(startX), int(startY), int(endX), int(endY)

				caixas.append([startX, startY, endX-startX, endY-startY])
				precisoes.append(float(confidence))

		caixas, precisoes = self._non_maxima_suppression(caixas, precisoes)
		return caixas, precisoes
