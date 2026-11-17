# language: es
Característica: Gestión de contratos por hitos, custodia Escrow y resolución de disputas
  Como usuario de Contrato Claro
  Quiero asegurar el ciclo de vida de contratos, fondos retenidos y arbitrajes
  Para garantizar transacciones transparentes entre freelancers y clientes

  Escenario: Creación de contrato por hitos y liberación progresiva hasta finalizar
    Dado que el sistema Contrato Claro está inicializado con usuarios registrados
    Cuando el freelancer "user-freelancer-1" crea el contrato "Diseño Identidad Visual" por 1000000 pesos con 2 hitos
    Entonces el contrato queda registrado en estado "Activo (Fondeado)" con 1000000 pesos en custodia
    Cuando se liberan los 2 hitos del contrato
    Entonces el estado final del contrato pasa a "Finalizado" y el saldo en custodia queda "Liberado"

  Escenario: Resolución de disputa comercial con reembolso al cliente
    Dado que existe un contrato activo por 800000 pesos con una disputa abierta
    Cuando el árbitro resuelve la disputa con la acción "devolver_cliente"
    Entonces el contrato pasa a estado "Cancelado con Reembolso" y el Escrow queda en "Reembolsado por Disputa"
