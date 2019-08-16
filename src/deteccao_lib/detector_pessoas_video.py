import time
import cv2 as cv
from threading import Thread

from imagelib import ktools
from imagelib.rastreadores.rastreador_cv import RastreadorCV as Rastreador
from videolib.videoStream import VideoStream
from deteccao_lib.detector_movimento_cv import DetectorMovimentoCV as DetectorMovimento
from deteccao_lib.detector_objetos_lib.detector_pessoas import DetectorPessoas
from deteccao_lib.pessoas_historico import PessoasHistorico
from deteccao_lib.caixas_objetos_lib.caixas_objetos import CaixasObjetos
from videolib.abstractVideoStream import AbstractVideoStream
from videolib.exceptions import CannotOpenStreamError, StreamClosedError, StreamStoppedError
from toolslib.ktools import LoopPeriodControl

class DetectorPessoasVideo(Thread):

    '''Detecta pessoas em um vídeo em uma thread separada.

    Deve-se configurar o objeto chamando os métodos 'configura_video'
    ou 'recebe_video', para haver uma entrada de vídeo, e
    'configura_detector', para configurar o detector de pessoas.

    Parameters
    -----------
    max_tempo_sem_deteccao : float, optional
        Tempo máximo que se pode ficar usando métodos mais leves de
        detecção, ao invés do principal. Em casos em que o detector seja
        leve, o valor pode ser 0 (i.e. sempre detectar).
        Deve ser positivo ou zero. (Padrão=5)
    max_tempo_parado : float, optional
        Tempo máximo que se pode ficar sem usar algum método de 
        detecção, nos casos em que o frame basicamente não se moveu.
        Deve ser positivo ou zero. (Padrão=60)
    max_largura_frame : int, optional
        Se o frame do vídeo for maior que este valor, ele será
        redimensionado. Deve ser positivo. (Padrão=700)
    usar_rastreamento : bool, optional
        Se for verdadeiro, o detector só será usado uma vez a cada
        período de tempo, e um rastreador será empregado para
        localizar as pessoas detectadas até o detector ser empregado
        de novo. (Padrão=False)

    Raises
    ------
    ValueError
        Se um dos argumentos não atender às especificações.
    '''

    def __init__(self, max_tempo_sem_deteccao=5.0, max_tempo_parado=60.0,
                 max_largura_frame=700, usar_rastreamento=False):

        super().__init__()
        
        self.usar_rastreamento = usar_rastreamento
        if max_tempo_sem_deteccao < 0:
            raise ValueError(
                "'max_tempo_sem_deteccao' deve ser um número positivo.")
        if max_tempo_parado <= 0:
            raise ValueError(
                "'max_tempo_parado' deve ser um número positivo ou zero.")
        if max_largura_frame <= 0:
            raise ValueError(
                "'max_largura_frame' deve ser um número positivo ou zero.")
        self.max_tempo_sem_deteccao = max_tempo_sem_deteccao
        self.max_tempo_parado = max_tempo_parado
        self.max_largura_frame = max_largura_frame

        self.pessoas_historico = PessoasHistorico()
        self.pessoas_registradas = CaixasObjetos()

        self.frame = None
        self.stream = None
        self.detectorPessoas = None
        self.stopped = False
        self.stream_externo = False

        self.modo = ''

    def configura_video(self, tipo, **keywords):

        '''Configura a entrada de vídeo internamente.

        Parameters
        -----------
        tipo : {'picamera', 'ipcamera', 'webcam', 'arquivo'}
        resolucao : (int, int)
            Se 'picamera' foi escolhido.
            Tupla que representa a resolução do vídeo. Ex.: (320, 240).
        fps : int
            Se 'picamera' foi escolhido.
            Frames por segundo.
        cameraURL : str
            Se 'ipcamera' foi escolhido.
            Url da câmera.
        login: str
            Se 'ipcamera' foi escolhido.
            Login da câmera.
        senha: str
            Se 'ipcamera' foi escolhido.
            Senha da câmera.
        idCam : str or int
            Se 'webcam' foi escolhido.
            Número da câmera. (padrão=0)
        arquivo : str
            Se 'arquivo' foi escolhido.
            Caminho ao arquivo.

        Returns
        -------
        self

        Raises
        -------
        CannotOpenStreamError
            Se não foi possível abrir o stream.

        See Also
        ---------
        recebe_video : Para receber um leitor de vídeo de fora.
        '''
        try:
            self.stream = VideoStream(tipo, **keywords)
        except (ImportError, CannotOpenStreamError):
            raise
        self.stream_externo = False

        # Para dar tempo de inicializar a câmera.
        time.sleep(2.0)

        return self

    def recebe_video(self, stream):
        '''Configura a entrada de vídeo com um objeto externo.

        Parameters
        -----------
        stream : AbstractVideoStream
            Objeto de entrada de vídeo que herda de AbstractVideoStream.
        '''
        if not isinstance(stream, AbstractVideoStream):
            raise TypeError("Stream deve herdar de 'AbstractVideoStream'.")
        self.stream = stream
        self.stream_externo = True
        return self

    def configura_detector(self, dir_modelo, tipo_modelo='yolo',
                           precisao_deteccao=0.4):

        '''Detecta pessoas usando um modelo de deep learning.

        Parameters
        -----------
        dir_modelo : str
            Destino do modelo desejado.
        tipo_modelo : {'yolo'}, optional
            Tipo do modelo.
        precisao_deteccao: float
            Quão precisa a detecção deve ser. Deve estar entre
            0.0 e 1.0 inclusive. (padrão=0.4)
        
        Raises
        --------
        ValueError
            Se o tipo do modelo for inválido.
        Exceções relacionadas ao OpenCV.
        '''

        try:
            self.detectorPessoas = DetectorPessoas(
                dir_modelo, tipo_modelo=tipo_modelo, precisao=precisao_deteccao)
        except Exception:
            raise

        return self

    def start(self):
        '''Executa o código principal em uma nova thread.

        Returns
        --------
        self
        '''
        super().start()
        return self

    def stop(self):
        '''Finaliza a thread.'''
        self.stopped = True

    def run(self):
        '''Detecta pessoas em um vídeo.'''

        MAX_TEMPO_ENTRE_REGISTROS = 1.0 #segundo
        PERIODO_MINIMO = 0.7 #segundo

        if self.stream is None or self.detectorPessoas is None:
            print('Erro: stream ou detector de pessoas não configurado.')
            return
        self.stream.start()
        time.sleep(2)
        
        detector_movimento = (
            DetectorMovimento(periodo_minimo=PERIODO_MINIMO)
            .recebe_video(self.stream)
            .start()
        )
        modo_deteccao = ModoDeteccao(
            detector_movimento, self.max_tempo_sem_deteccao,
            self.max_tempo_parado, self.usar_rastreamento
        )
        rastreador = Rastreador()
        controla_periodo_loop = LoopPeriodControl(PERIODO_MINIMO)
        
        while not self.stopped:
            
            tempo_comeco_iteracao = time.time()
            try:
                frame = self.stream.read()
            except (StreamClosedError, StreamStoppedError) as e:
                print('Não foi possível ler frame.')
                break

            # Redimensiona imagem para diminuir os gastos de detecção 
            # de movimento.
            frame = self._frame_tamanho_maximo(frame)

            # Decide se o loop estará no modo 'detectando', 
            # 'rastreando' ou 'parado'.
            modo = modo_deteccao.atualiza_modo(frame)
            
            if modo == 'detectando':
                try:
                    caixas, pesos = self.detectorPessoas.detectar(frame)
                except Exception as e:
                    print('Erro de detecção:\n\t[{}]: {}'
                        .format(type(e).__name__, str(e)))
                    break
            elif modo == 'rastreando':
                if modo_deteccao.mudou_modo():
                    rastreador.reiniciar()
                    rastreador.adiciona_rastreadores(
                        frame,
                        self.pessoas_registradas.pega_objetos(retorna_peso=False)
                    )
                caixas = rastreador.atualiza(frame)
                pesos = []
            else: #modo == 'parado':
                caixas, pesos = [], []

            # Se a iteração for muito lenta, reiniciar o registro.
            if time.time()-tempo_comeco_iteracao > MAX_TEMPO_ENTRE_REGISTROS:
                self.pessoas_registradas.reiniciar()

            caixas, pesos = self.pessoas_registradas.atualizar(
                caixas, pesos, caixas_paradas=(modo=='parado')
            )
            self.frame = frame.copy()
            self.modo = modo

            # Salva o numero de pessoas registradas neste ciclo.
            self.pessoas_historico.atualiza_periodo(len(caixas))
            # Período do loop >= 'PERIODO_MINIMO'.
            controla_periodo_loop.force_minimum_loop_period()

        detector_movimento.stop()
        if not self.stream_externo:
            self.stream.stop()
        self.stop()


    def pega_quantidade_pessoas(self):
        '''Retorna o número de pessoas registradas no momento.
        
        Returns
        -------
        int
        '''
        return len(self.pessoas_registradas)

    def pega_frame(self, mostrar_caixas=False, mostrar_precisao=False, mostrar_modo=False):
        '''Retorna o último frame analizado.
        
        Parameters
        -----------
        mostrar_caixas : bool, optional
            Se as caixas que representam as pessoas devem ser 
            desenhadas na tela. (Padrão=False)
        mostrar_precisao : bool, optional
            Se a precisão de detecção deve ser desenhada em cima das
            caixas. Se 'mostrar_caixas' for falso esta opção também
            será. (Padrão=False)
        mostrar_modo : bool,, optional
            Se o modo de detecção da última iteração deve ser escrito.
            (Padrão=False)

        Returns
        --------
        numpy.ndarray
            Frame a ser retornado. Antes de qualquer frame ser lido
            da fonte, retorna uma imagem preta de mesmas dimensões do
            vídeo.
        '''

        if self.frame is None:
            return self._frame_tamanho_maximo(
                ktools.black_image(*self.stream.pega_dimensoes())
            )
        
        frame = self.frame.copy()

        if mostrar_modo:
            ktools.write(frame, self.modo, x=10, y=frame.shape[0]-10, outline=True)

        if not mostrar_caixas:
            return frame
        
        caixas, pesos = self.pessoas_registradas.pega_objetos()
        frame = ktools.draw_boxes(
            frame, boxes=caixas, infos=pesos, write_infos=mostrar_precisao)
        
        return frame


    def pega_dados_periodo(self):
        '''Retorna dados coletados desde a última chamada (ou início).

        Returns
        --------
        media : float
            Média ponderada dos valores com o intervalo de tempo.
        max_valor : float
            Valor máximo recebido.
        min_valor : float
            Valor mínimo recebido.
        tempo_decorrido : float
            Tempo total decorrido.
        '''
        return self.pessoas_historico.finaliza_periodo()
    
    def _frame_tamanho_maximo(self, frame):
        return ktools.resize(frame, min(self.max_largura_frame, frame.shape[1]))



class ModoDeteccao:

    '''Escolhe o modo de detecção de um loop em DeteccaoPessoasVideo.
    
    Parameters
    -----------
    detector_movimento : imagelib.detector_movimento.DetectorMovimento
        Objeto que detecta movimento em um vídeo. Assume-se que já 
        esteja configurado e iniciado.
    max_tempo_sem_deteccao : float
        Tempo máximo que se pode ficar usando métodos mais leves de
        detecção, ao invés do principal. Em casos em que o detector seja
        leve, o valor pode ser 0 (i.e. sempre detectar).
        Deve ser positivo ou zero.
    max_tempo_parado : float
        Tempo máximo que se pode ficar sem usar algum método de 
        detecção, nos casos em que o frame basicamente não se moveu.
        Deve ser positivo ou zero.
    usar_rastreamento : bool
        Se for verdadeiro, o detector só será usado uma vez a cada
        período de tempo, e um rastreador será empregado para
        localizar as pessoas detectadas até o detector ser empregado
        de novo.
    max_tempo_sem_atualizar_modo : int, optional
        Tempo máximo entre duas atualizações de modo para que se possa
        usar o rastreamento de pessoas. (Padrão=1)
    '''

    def __init__(self, detector_movimento, max_tempo_sem_deteccao, 
                 max_tempo_parado, usar_rastreamento, 
                 max_tempo_sem_atualizar_modo=1):

        self.detector_movimento = detector_movimento
        self.max_tempo_sem_deteccao = max_tempo_sem_deteccao
        self.max_tempo_parado = max_tempo_parado
        self.max_tempo_sem_atualizar_modo = max_tempo_sem_atualizar_modo
        self.usar_rastreamento = usar_rastreamento

        self.tempo_em_que_parou = time.time()-self.max_tempo_parado
        self.tempo_ultima_deteccao = time.time()-self.max_tempo_sem_deteccao

        self.modo = ''
        self.modo_anterior = ''
        self.tempo_ultima_checagem = time.time()
    
    def atualiza_modo(self, frame):
        '''Atualiza o modo no qual a detecção se encontra.
        Parameters
        -----------
        frame : numpy.ndarray
            Frame do vídeo, que será usado na decisão do modo.
        Returns
        --------
        str
            Modo decidido.
        '''
        self.modo_anterior = self.modo
        self.checagem_atual = time.time()

        teve_movimento = self.detector_movimento.houve_mudanca()
        parado_demais = time.time()-self.tempo_em_que_parou >= self.max_tempo_parado
        sem_detectar_demais = \
            time.time()-self.tempo_ultima_deteccao >= self.max_tempo_sem_deteccao
        max_tempo_checagem_excedido = self.tempo_ultima_checagem-self.checagem_atual > self.max_tempo_sem_atualizar_modo
    
        # print(
        #     'Teve movimento? \t{}\n'
        #     'Parado demais? \t\t{}\n'
        #     'Sem detectar demais? \t{}\n\n'
        #     .format(teve_movimento, parado_demais, sem_detectar_demais)
        # )
        if self.modo_anterior == 'detectando':
            if not teve_movimento:
                self.modo = 'parado'
            elif not self.usar_rastreamento or max_tempo_checagem_excedido:
                self.modo = 'detectando'
            else:
                self.modo = 'rastreando'
        elif self.modo_anterior == 'parado':
            if teve_movimento or parado_demais:
                self.modo = 'detectando'
            else:
                self.modo = 'parado'
        elif self.modo_anterior == 'rastreando':
            if not teve_movimento or sem_detectar_demais or max_tempo_checagem_excedido:
                self.modo = 'detectando'
        
        else:
            self.modo = 'detectando'
        
        if self.modo == 'parado' and self.modo_anterior != 'parado':
            self.tempo_em_que_parou = time.time()
        elif self.modo == 'detectando':
            self.tempo_ultima_deteccao = time.time()
        
        self.tempo_ultima_checagem = time.time()
        return self.modo

    def mudou_modo(self):
        '''Retorna se o modo mudou ou não desde a última atualização
        Returns
        --------
        bool
        '''
        return self.modo != self.modo_anterior