import os

from deteccao_objetos_lib.detector_objetos_lib.detector_objetos_yolo import DetectorObjetosYolo

DEFAULT_PRECISAO_DETECCAO = 0.4
DEFAULT_SUPRESSAO_DETECCAO = 0.3

class DetectorPessoas:

	'''Detecta pessoas usando um modelo de deep learning.

	Parameters
	-----------
	path_modelo : str
		Destino do modelo desejado.
	tipo_modelo : {'yolo'}. optional
		Tipo do modelo.
	precisao : float, optional
		Quão precisa a detecção deve ser. Deve estar entre 0.0 e 1.0 incl.
	supressao : float, optional
		Quão próximas as detecções de pessoas devem estar para
		serem consideradas as mesmas. Deve estar entre 0.0 e 1.0 incl.

	Raises
	-------
	ValueError
		Se o tipo do modelo for invalido.
	Exceções relacionadas ao OpenCV
	'''

	def __init__(self, path_modelo, tipo_modelo='yolo', precisao=DEFAULT_PRECISAO_DETECCAO,
				 supressao=DEFAULT_SUPRESSAO_DETECCAO):
		
		if not os.path.isdir(path_modelo):
			path_modelo = os.path.join(os.getcwd(), path_modelo)

		path_modelo = os.path.abspath(path_modelo)

		if tipo_modelo == 'yolo':
			self.detector = DetectorObjetosYolo(
				path_modelo, rotulos=['person'],
				precisao_minima=precisao, supressao_caixas=supressao
			)
		# elif tipo_modelo == 'ssd':
		# 	self.detector = DetectorPessoasSSD(path_modelo, precisao, supressao)
		else:
			raise ValueError('Tipo do modelo invalido.')

	def detectar(self, input_image):
		'''Detecta pessoas em uma imagem.

		Parameters
		-----------
		input_image : numpy.ndarray
			Imagem a ser analizada.
		
		Returns
		--------
		caixas : [(int, int, int, int), ...]
			Caixas que representam pessosa em uma imagem. Cada tupla 
			é composta por (x, y, w, h), ou seja, as coordenadas x e y,
			a largura e a altura.
		precisoes : [float, ...]
			A probabilidade de cada caixa ser uma pessoa. Os valores 
			variam entre 0.0 e 1.0.
		'''
		return self.detector.detectar(input_image)['person']
