# Lab 3 — Advanced RAG with Azure AI Search × Copilot Studio (Guía Paso a Paso)

## Descripción General
Este laboratorio te guiará paso a paso en la implementación de un sistema RAG (Retrieval-Augmented Generation) avanzado usando Azure AI Search integrado con Copilot Studio. Aprenderás a diseñar índices optimizados, implementar búsquedas híbridas y crear agentes inteligentes.

## Requisitos Previos
- [ ] Suscripción activa de Azure
- [ ] Acceso a Microsoft Copilot Studio
- [ ] Azure CLI instalado
- [ ] Visual Studio Code (opcional)
- [ ] Conocimientos básicos de REST APIs
- [ ] Datos de ejemplo para indexar (documentos PDF, DOCX, o texto)

---

## Parte 1: Configuración de Azure AI Search

### Paso 1.1: Crear el Servicio de Azure AI Search

1. Inicia sesión en [Azure Portal](https://portal.azure.com)
2. Haz clic en **"Create a resource"**
3. Busca **"Azure AI Search"**
4. Completa el formulario:
   - **Subscription**: Selecciona tu suscripción
   - **Resource Group**: Crea uno nuevo o usa existente (ej: `rg-copilot-rag-lab`)
   - **Service name**: Nombre único (ej: `aisearch-copilot-lab-001`)
   - **Location**: Selecciona la región más cercana
   - **Pricing tier**: Selecciona **Standard** o superior (necesario para semantic ranker)
5. Haz clic en **"Review + create"** y luego **"Create"**
6. Espera a que se complete el despliegue (2-3 minutos)

### Paso 1.2: Obtener las Credenciales de Acceso

1. Ve al recurso de Azure AI Search recién creado
2. En el menú izquierdo, selecciona **"Keys"**
3. Copia y guarda:
   - **URL** (ej: `https://aisearch-copilot-lab-001.search.windows.net`)
   - **Primary admin key**
4. Guarda estas credenciales en un lugar seguro (las necesitarás más adelante)

### Paso 1.3: Crear un Storage Account para Datos de Origen

1. En Azure Portal, crea un nuevo **Storage Account**:
   - **Name**: `stcopilotraglab001`
   - **Performance**: Standard
   - **Replication**: LRS (para desarrollo)
2. Una vez creado, ve a **"Containers"** y crea un nuevo contenedor:
   - **Name**: `documents`
   - **Public access level**: Private
3. Sube documentos de ejemplo (PDF, DOCX, TXT) al contenedor

### Paso 1.4: Diseñar el Esquema del Índice

1. Ve a tu servicio Azure AI Search
2. Selecciona **"Indexes"** en el menú izquierdo
3. Haz clic en **"+ Add index"**
4. Selecciona **"JSON"** para editar el esquema completo
5. Pega la siguiente configuración completa:

```json
{
  "name": "rag-knowledge-index",
  "fields": [
    {
      "name": "chunk_id",
      "type": "Edm.String",
      "key": true,
      "searchable": false
    },
    {
      "name": "chunk_text",
      "type": "Edm.String",
      "searchable": true,
      "analyzer": "en.microsoft"
    },
    {
      "name": "chunk_vector",
      "type": "Collection(Edm.Single)",
      "searchable": true,
      "dimensions": 1536,
      "vectorSearchProfile": "vector-profile-1"
    },
    {
      "name": "source_url",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "facetable": true
    },
    {
      "name": "tags",
      "type": "Collection(Edm.String)",
      "searchable": true,
      "filterable": true,
      "facetable": true
    },
    {
      "name": "locale",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true
    },
    {
      "name": "created_date",
      "type": "Edm.DateTimeOffset",
      "filterable": true,
      "sortable": true
    }
  ],
  "vectorSearch": {
    "algorithms": [
      {
        "name": "hnsw-algorithm-1",
        "kind": "hnsw",
        "hnswParameters": {
          "metric": "cosine",
          "m": 4,
          "efConstruction": 400,
          "efSearch": 500
        }
      }
    ],
    "profiles": [
      {
        "name": "vector-profile-1",
        "algorithm": "hnsw-algorithm-1",
        "vectorizer": "openai-vectorizer-1"
      }
    ],
    "vectorizers": [
      {
        "name": "openai-vectorizer-1",
        "kind": "azureOpenAI",
        "azureOpenAIParameters": {
          "resourceUri": "https://YOUR-OPENAI-RESOURCE.openai.azure.com",
          "deploymentId": "text-embedding-ada-002",
          "apiKey": "YOUR-OPENAI-API-KEY"
        }
      }
    ]
  },
  "semantic": {
    "configurations": [
      {
        "name": "semantic-config-1",
        "prioritizedFields": {
          "titleField": "chunk_text",
          "contentFields": [
            "chunk_text"
          ],
          "keywordsFields": [
            "tags"
          ]
        }
      }
    ]
  }
}
```

6. **Personaliza estos valores antes de crear el índice**:
   - `resourceUri`: Cambia por tu endpoint de Azure OpenAI (ej: `https://myopenai.openai.azure.com`)
   - `deploymentId`: Cambia por el nombre de tu deployment de embeddings
   - `apiKey`: Usa tu API key de Azure OpenAI (o mejor aún, configura Managed Identity)
   - `dimensions`: 1536 para `text-embedding-ada-002`, 3072 para `text-embedding-3-large`

7. Haz clic en **"Create"**

#### Explicación de los Parámetros del Vector Profile:

**Algoritmo HNSW (Hierarchical Navigable Small World)**:
- `metric`: `cosine` - Mide similitud entre vectores (-1 a 1, donde 1 es idéntico)
- `m`: `4` - Número de conexiones bidireccionales por nodo (más = mejor recall, más memoria)
- `efConstruction`: `400` - Precisión durante indexación (100-1000, más = mejor calidad, más lento)
- `efSearch`: `500` - Precisión durante búsqueda (100-1000, más = mejores resultados, más lento)

**Vectorizer**:
- Integra Azure OpenAI directamente en el índice
- Genera embeddings automáticamente durante la indexación
- También se usa para convertir queries a vectores

### Paso 1.5: Crear un Indexer con Skillset

1. En Azure AI Search, ve a **"Indexers"**
2. Haz clic en **"+ Add indexer"**
3. Configura el Data Source:
   - **Data source type**: Azure Blob Storage
   - **Connection string**: Tu Storage Account
   - **Container**: `documents`
4. Configura el Skillset:
   - Agrega **Document Cracking** skill
   - Agrega **Text Split** skill (chunking):
     - Text split mode: pages
     - Maximum page length: 1000 caracteres
     - Page overlap length: 200 caracteres
   - Agrega **Azure OpenAI Embedding** skill:
     - Model: text-embedding-ada-002
     - Deployment name: Tu deployment de embeddings
5. Mapea los campos de salida a tu índice
6. Configura el schedule: **Once** (para pruebas) o **Hourly**
7. Haz clic en **"Submit"** y espera a que complete

### Paso 1.6: Validar la Indexación

1. Ve a **"Search explorer"** en tu índice
2. Ejecuta una consulta de prueba:
```json
{
  "search": "*",
  "top": 5
}
```
3. Verifica que los documentos se hayan indexado correctamente
4. Revisa que los campos `chunk_text`, `chunk_vector`, y `source_url` tengan datos

---

## Parte 2: Probar Patrones de Consulta

### Paso 2.1: Consulta de Texto Simple (BM25)

1. En **Search explorer**, ejecuta:
```json
{
  "search": "azure cognitive services",
  "searchMode": "all",
  "top": 5,
  "select": "chunk_id,chunk_text,source_url"
}
```
2. Observa los resultados y el score de relevancia

### Paso 2.2: Consulta Vectorial

1. Primero, obtén el embedding de tu consulta usando Azure OpenAI:
```powershell
# Llama a tu endpoint de Azure OpenAI para obtener el embedding
$query = "What are the benefits of Azure AI Search?"
# Obtén el vector (esto devolverá un array de 1536 números)
```

2. Ejecuta la consulta vectorial:
```json
{
  "vectorQueries": [
    {
      "kind": "vector",
      "vector": [0.123, -0.456, ...], 
      "fields": "chunk_vector",
      "k": 5
    }
  ],
  "select": "chunk_id,chunk_text,source_url"
}
```

### Paso 2.3: Consulta Híbrida (BM25 + Vector)

```json
{
  "search": "azure cognitive services",
  "vectorQueries": [
    {
      "kind": "vector",
      "vector": [0.123, -0.456, ...],
      "fields": "chunk_vector",
      "k": 50
    }
  ],
  "top": 5,
  "select": "chunk_id,chunk_text,source_url"
}
```

### Paso 2.4: Activar Semantic Ranker

```json
{
  "search": "How to implement RAG with Azure?",
  "vectorQueries": [
    {
      "kind": "vector",
      "vector": [0.123, -0.456, ...],
      "fields": "chunk_vector",
      "k": 50
    }
  ],
  "queryType": "semantic",
  "semanticConfiguration": "default",
  "top": 5,
  "select": "chunk_id,chunk_text,source_url",
  "answers": "extractive|count-3",
  "captions": "extractive|highlight-true"
}
```

### Paso 2.5: Aplicar Filtros

```json
{
  "search": "azure ai",
  "filter": "locale eq 'en-US' and tags/any(t: t eq 'documentation')",
  "top": 5
}
```

---

## Parte 3: Integración con Copilot Studio

### Opción A: Usando Knowledge Source (Método Rápido)

#### Paso 3A.1: Crear un Agente en Copilot Studio

1. Ve a [Copilot Studio](https://copilotstudio.microsoft.com)
2. Haz clic en **"Create"** > **"New agent"**
3. Dale un nombre: `RAG Assistant with AI Search`
4. Selecciona el idioma: Español o Inglés
5. Haz clic en **"Create"**

#### Paso 3A.2: Agregar Knowledge Source

1. En tu agente, ve a **"Knowledge"** en el menú izquierdo
2. Haz clic en **"+ Add knowledge"**
3. Selecciona **"Azure AI Search"**
4. Completa la configuración:
   - **Service URL**: Tu URL de AI Search
   - **API Key**: Tu admin key
   - **Index name**: `rag-knowledge-index`
5. Haz clic en **"Add"**

#### Paso 3A.3: Configurar el Agente

1. Ve a **"Settings"** > **"AI capabilities"**
2. Habilita:
   - ✓ Use GPT for generative answers
   - ✓ Search knowledge sources
3. En **"Generative answers"**, selecciona:
   - Content moderation: Medium
   - Include citations: Yes

#### Paso 3A.4: Probar el Agente

1. Haz clic en **"Test"** en la esquina superior derecha
2. Escribe preguntas relacionadas con tus documentos:
   - "¿Cuáles son los beneficios de Azure AI Search?"
   - "Explícame cómo funciona el semantic ranker"
3. Verifica que el agente cite las fuentes correctamente

---

### Opción B: Usando HTTP Connector (Control Completo)

#### Paso 3B.1: Crear un Azure Function para Abstraer la API

1. Crea una nueva Azure Function (Python o C#):
```python
import azure.functions as func
import json
import requests
import os

def main(req: func.HttpRequest) -> func.HttpResponse:
    # Obtener parámetros
    user_query = req.params.get('query')
    filters = req.params.get('filters', '')
    
    # Endpoint de Azure AI Search
    search_url = f"{os.environ['SEARCH_ENDPOINT']}/indexes/{os.environ['INDEX_NAME']}/docs/search?api-version=2023-11-01"
    
    # Construir payload
    payload = {
        "search": user_query,
        "top": 5,
        "select": "chunk_text,source_url",
        "filter": filters if filters else None
    }
    
    # Llamar a AI Search
    headers = {
        "Content-Type": "application/json",
        "api-key": os.environ['SEARCH_API_KEY']
    }
    
    response = requests.post(search_url, json=payload, headers=headers)
    
    return func.HttpResponse(
        body=json.dumps(response.json()),
        mimetype="application/json",
        status_code=200
    )
```

2. Despliega la función a Azure
3. Obtén la URL de la función

#### Paso 3B.2: Crear un Custom Connector en Copilot Studio

1. En Copilot Studio, ve a tu agente
2. Selecciona **"Actions"** > **"+ Add an action"**
3. Selecciona **"Create a connector"**
4. Elige **"HTTP"** como tipo de conector

#### Paso 3B.3: Configurar el Connector

1. **General Settings**:
   - Name: `Search RAG Knowledge`
   - Description: `Busca información relevante en la base de conocimiento`
   
2. **Request**:
   - Method: POST
   - URL: `[URL_DE_TU_AZURE_FUNCTION]`
   - Headers:
     - `Content-Type`: `application/json`
   
3. **Input Parameters**:
   - `query` (string, required): La pregunta del usuario
   - `filters` (string, optional): Filtros OData

4. **Response**:
   - Parse automáticamente o define el schema:
```json
{
  "type": "object",
  "properties": {
    "value": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "chunk_text": {"type": "string"},
          "source_url": {"type": "string"}
        }
      }
    }
  }
}
```

5. Haz clic en **"Save"**

#### Paso 3B.4: Crear un Tool en el Agente

1. Ve a **"Actions"** > **"Tools"**
2. Haz clic en **"+ Add a tool"**
3. Selecciona el connector `Search RAG Knowledge`
4. Configura:
   - Tool name: `searchRagKnowledge`
   - Description: `Busca información relevante cuando el usuario hace preguntas sobre [tu dominio]`

#### Paso 3B.5: Configurar las Instructions del Agente

1. Ve a **"Instructions"** en el menú del agente
2. Agrega las siguientes instrucciones:

```
Eres un asistente experto en [tu dominio].

Cuando el usuario haga una pregunta:
1. Usa la herramienta searchRagKnowledge para buscar información relevante
2. Analiza los resultados obtenidos
3. Formula una respuesta completa y precisa basada en la información encontrada
4. SIEMPRE incluye las citas de las fuentes usando el formato: [Fuente](URL)
5. Si no encuentras información relevante, indícalo claramente

Tono: Profesional y amigable
Formato: Usa listas y formato markdown cuando sea apropiado
```

3. Haz clic en **"Save"**

#### Paso 3B.6: Probar la Integración

1. Abre el **Test panel**
2. Escribe: "¿Qué información tienes sobre Azure AI Search?"
3. Verifica que:
   - El agente llame al tool `searchRagKnowledge`
   - Se muestren los resultados de la búsqueda
   - La respuesta incluya citas con URLs

---

### Opción C: Real-time Knowledge Connectors

#### Paso 3C.1: Configurar Microsoft Graph Connector (Si aplica)

1. Si tus datos están en SharePoint o Microsoft 365:
2. Ve a **"Knowledge"** > **"+ Add knowledge"**
3. Selecciona **"SharePoint"** o **"Microsoft 365"**
4. Autoriza el acceso
5. Selecciona los sitios o carpetas a indexar

#### Paso 3C.2: Configurar Connector para Datos Externos

1. Si usas Salesforce, ServiceNow, u otro sistema:
2. Usa **Microsoft Graph connectors** para federación
3. O implementa un webhook que se actualice en tiempo real

---

## Parte 4: Orquestación Avanzada del Agente

### Paso 4.1: Agregar Prompt Tool para Post-Procesamiento

1. Ve a **"Tools"** > **"+ Add a tool"**
2. Selecciona **"Prompt"**
3. Configura:
   - Name: `summarizeWithCitations`
   - Description: `Resume la información y agrega citas`
   - Prompt:
```
Dada la siguiente información de búsqueda:
{searchResults}

Resume los puntos clave en 3-5 bullets.
Incluye las citas en formato [Fuente](URL).
Mantén un tono profesional.
Verifica que no haya información PII sensible.
```

### Paso 4.2: Crear un Flujo Conversacional Complejo

1. Ve a **"Topics"** > **"+ New topic"**
2. Crea un topic: `Complex RAG Query`
3. Agrega los siguientes nodos:

```
[Trigger] Usuario hace pregunta compleja
   ↓
[Question] "¿Quieres que busque en toda la base de datos o en documentos específicos?"
   ↓
[Condition] Si "específicos" → Pedir categoría
   ↓
[Action] Llamar tool searchRagKnowledge con filtros
   ↓
[Action] Llamar tool summarizeWithCitations
   ↓
[Message] Mostrar resumen con citas
   ↓
[Question] "¿Necesitas más detalles sobre algún punto?"
   ↓
[Loop back if yes]
```

### Paso 4.3: Implementar Logging y Analytics

1. Ve a **"Settings"** > **"Analytics"**
2. Habilita:
   - Conversation logging
   - Tool usage tracking
   - User satisfaction metrics
3. Configura exportación a Application Insights (opcional)

### Paso 4.4: Agregar Manejo de Errores

1. En tus tools, agrega lógica de fallback
2. En **Instructions**, agrega:
```
Si searchRagKnowledge falla:
- Intenta una segunda vez con una consulta simplificada
- Si falla de nuevo, informa al usuario: "Lo siento, no puedo acceder a la base de conocimiento en este momento"
- Ofrece alternativas: "¿Puedo ayudarte con otra cosa?"
```

---

## Parte 5: Mejores Prácticas y Optimización

### Paso 5.1: Optimizar Chunking

1. Vuelve a tu Indexer en Azure AI Search
2. Experimenta con diferentes tamaños:
   - **Documentos técnicos**: 800-1000 caracteres
   - **Artículos largos**: 1200-1500 caracteres
   - **FAQs cortos**: 400-600 caracteres
3. Ajusta el overlap: 15-20% del tamaño del chunk

### Paso 5.2: Configurar Semantic Ranker para Producción

1. En Azure AI Search, verifica que el tier sea **Standard** o superior
2. Configura la semantic configuration:
```json
{
  "name": "default",
  "prioritizedFields": {
    "titleField": {
      "fieldName": "chunk_text"
    },
    "contentFields": [
      {
        "fieldName": "chunk_text"
      }
    ],
    "keywordsFields": [
      {
        "fieldName": "tags"
      }
    ]
  }
}
```

### Paso 5.3: Implementar Scoring Profiles

1. Crea un scoring profile para priorizar documentos recientes:
```json
{
  "name": "recentDocuments",
  "functions": [
    {
      "type": "freshness",
      "fieldName": "created_date",
      "boost": 2,
      "interpolation": "linear",
      "freshness": {
        "boostingDuration": "P30D"
      }
    }
  ]
}
```

### Paso 5.4: Monitorear el Payload Size

1. En Copilot Studio, el límite de connector response es **~450 KB**
2. Optimiza los campos select:
```json
{
  "select": "chunk_text,source_url",
  "top": 5
}
```
3. Implementa paginación si necesitas más resultados

### Paso 5.5: Seguridad y Compliance

1. **Habilitar Private Link**:
   - En Azure AI Search, ve a **"Networking"**
   - Configura **Private endpoint**
   - Conecta con tu VNET

2. **Usar Managed Identity**:
   - Configura Managed Identity en tu Azure Function
   - Otorga permisos de **Search Index Data Reader** al MI
   - Elimina el uso de API keys

3. **Implementar RBAC**:
   - Usa Azure RBAC en lugar de API keys
   - Roles recomendados: Search Service Contributor, Search Index Data Contributor

---

## Parte 6: Evaluación y Métricas

### Paso 6.1: Configurar Métricas de Recuperación

1. Implementa logging en tu Azure Function:
```python
import logging

# Log queries and results
logging.info(f"Query: {user_query}, Results: {len(results)}, Latency: {latency_ms}ms")
```

2. Exporta logs a **Application Insights**

### Paso 6.2: Evaluar Calidad de Recuperación

Usa las siguientes métricas:

1. **NDCG (Normalized Discounted Cumulative Gain)**
   - Mide la relevancia de los resultados
   - Objetivo: > 0.7

2. **Precision@K**
   - % de resultados relevantes en top K
   - Objetivo: > 80% para K=5

3. **Recall**
   - % de documentos relevantes recuperados
   - Objetivo: > 75%

### Paso 6.3: Monitorear Latencia

1. En Azure AI Search, ve a **"Metrics"**
2. Monitorea:
   - Search Latency (objetivo: < 500ms)
   - Search QPS (queries per second)
   - Throttled queries (objetivo: 0%)

### Paso 6.4: Recolectar Feedback de Usuarios

1. En Copilot Studio, agrega al final de cada conversación:
```
[Question] "¿Esta respuesta fue útil?"
[Options] 👍 Sí | 👎 No
[If No] "¿Qué podría mejorar?"
```

2. Exporta los resultados para análisis

### Paso 6.5: A/B Testing

1. Crea dos versiones del agente:
   - Versión A: Solo búsqueda vectorial
   - Versión B: Búsqueda híbrida + semantic ranker
2. Distribuye 50/50 del tráfico
3. Compara métricas de satisfacción después de 1-2 semanas

---

## Parte 7: Limpieza de Recursos

### Paso 7.1: Eliminar el Agente de Copilot Studio

1. Ve a Copilot Studio
2. Selecciona tu agente
3. Ve a **"Settings"** > **"General"**
4. Haz clic en **"Delete agent"**
5. Confirma la eliminación

### Paso 7.2: Eliminar Azure AI Search Resources

1. Ve a Azure Portal
2. Navega a tu Resource Group (`rg-copilot-rag-lab`)
3. Selecciona el servicio Azure AI Search
4. Haz clic en **"Delete"**
5. Escribe el nombre del servicio para confirmar

### Paso 7.3: Eliminar Storage Account

1. En el mismo Resource Group
2. Selecciona el Storage Account
3. Haz clic en **"Delete"**
4. Confirma

### Paso 7.4: Eliminar Azure Function (si creaste una)

1. Selecciona el Function App
2. Haz clic en **"Delete"**
3. Confirma

### Paso 7.5: Eliminar el Resource Group Completo

1. Selecciona el Resource Group
2. Haz clic en **"Delete resource group"**
3. Escribe el nombre del grupo para confirmar
4. Haz clic en **"Delete"**

**Nota**: Esto eliminará todos los recursos dentro del grupo de manera permanente.

---

## Checklist Final

### Implementación Exitosa ✓
- [ ] Azure AI Search creado y configurado
- [ ] Índice con campos de texto y vectores creado
- [ ] Datos indexados correctamente con chunking
- [ ] Consultas híbridas y semantic ranker funcionando
- [ ] Agente de Copilot Studio creado
- [ ] Knowledge source o HTTP connector integrado
- [ ] Tools y prompts configurados
- [ ] Pruebas funcionales completadas
- [ ] Métricas de evaluación establecidas

### Optimización y Producción ✓
- [ ] Chunking optimizado para tu caso de uso
- [ ] Scoring profiles configurados (si aplica)
- [ ] Security (Private Link, RBAC) implementado
- [ ] Logging y monitoring habilitados
- [ ] Feedback loop establecido
- [ ] Documentación creada para el equipo

---

## Recursos Adicionales

### Documentación Oficial
- [Azure AI Search Documentation](https://learn.microsoft.com/azure/search/)
- [Copilot Studio Documentation](https://learn.microsoft.com/microsoft-copilot-studio/)
- [RAG Patterns](https://learn.microsoft.com/azure/architecture/ai-ml/guide/rag/rag-solution-design-and-evaluation-guide)

### Ejemplos de Código
- [Azure Search Python SDK](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/search)
- [Copilot Studio Samples](https://github.com/microsoft/copilot-studio-samples)

### Tutoriales Relacionados
- Vector Search in Azure AI Search
- Building RAG Applications
- Semantic Ranking Best Practices

---

## Troubleshooting Común

### Problema: El índice no muestra resultados
**Solución**: 
1. Verifica que el indexer haya completado sin errores
2. Revisa los logs del indexer en Azure Portal
3. Confirma que el skillset esté configurado correctamente

### Problema: Las consultas vectoriales no devuelven resultados relevantes
**Solución**:
1. Verifica que el modelo de embeddings sea consistente (indexación vs. query)
2. Aumenta el valor de K en vectorQueries
3. Considera usar búsqueda híbrida en lugar de solo vectorial

### Problema: El connector de Copilot Studio falla
**Solución**:
1. Verifica la URL y API key
2. Revisa que el payload response sea < 450 KB
3. Valida el schema de respuesta en el connector

### Problema: Alta latencia en las respuestas
**Solución**:
1. Reduce el número de resultados (top)
2. Minimiza los campos en select
3. Considera usar caché en Azure Function
4. Verifica el tier de Azure AI Search (scale up si es necesario)

---

**¡Felicidades!** Has completado el laboratorio de RAG avanzado con Azure AI Search y Copilot Studio. 🎉

¿Preguntas o problemas? Consulta la documentación oficial o abre un issue en el repositorio del curso.
