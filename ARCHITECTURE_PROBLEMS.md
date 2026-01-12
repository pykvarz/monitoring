# Архитектурные проблемы - Network Monitor

**Дата**: 2026-01-12  
**Версия**: 2.1  
**Статус**: 🏗️ Анализ архитектуры

---

## 🏗️ Обзор текущей архитектуры

### Структура проекта:

```
Network Monitor/
├── MainWindow (661 строк) - Главное окно
├── Менеджеры:
│   ├── FilterManager (фильтрация)
│   ├── ThemeManager (темы)
│   ├── DashboardManager (статистика)
│   └── ExportImportManager (импорт/экспорт)
├── Сервисы:
│   ├── StorageManager (хранение)
│   ├── PingService (ping)
│   └── NotificationService (уведомления)
└── Модели: Host, AppConfig, HostStatus
```

---

## 🚨 Найденные архитектурные проблемы

### 1. ❌ **Нарушение Dependency Inversion Principle (DIP)**

**Приоритет**: 🔴 **КРИТИЧЕСКИЙ**

#### Проблема:
Классы зависят от конкретных реализаций, а не от абстракций.

#### MainWindow → StorageManager (жесткая зависимость)

```python
# main_window.py, строка 60
class MainWindow(QMainWindow):
    def __init__(self):
        self._storage = StorageManager()  # ❌ Прямое создание!
```

**Почему это плохо:**
- ❌ Невозможно подменить StorageManager на тестовый
- ❌ Невозможно использовать другие хранилища (БД, cloud)
- ❌ MainWindow жестко привязан к конкретной реализации
- ❌ Нарушение принципа инверсии зависимостей

#### ThemeManager → StorageManager (такая же проблема)

```python
# theme_manager.py, строка 29-44
class ThemeManager:
    def __init__(self, main_window: QMainWindow, config: AppConfig, 
                 storage: StorageManager, ...):  # ✅ Передается через DI
        self._storage = storage  # ✅ Хорошо, но...
        
    def toggle_theme(self):
        self._storage.save_config(self._config)  # ❌ Прямой вызов!
```

**Проблема**: ThemeManager знает о внутреннем API StorageManager.

---

### 2. ❌ **Нарушение Single Responsibility Principle (SRP)**

**Приоритет**: 🔴 **ВЫСОКИЙ**

#### MainWindow делает слишком много:

```python
class MainWindow:
    # 1. Управление UI
    def _init_ui(self): ...
    
    # 2. Управление данными
    def _load_table(self): ...
    def _modify_hosts_safely(self): ...
    
    # 3. Координация менеджеров
    def _init_managers(self): ...
    
    # 4. Обработка событий мониторинга
    def _on_status_updated(self): ...
    
    # 5. Создание контекстных меню
    def _show_context_menu(self): ...
    def _show_bulk_menu(self): ...
    def _show_header_context_menu(self): ...
    
    # 6. Работа с настройками таблицы
    def _on_column_resized(self): ...
    def _on_column_moved(self): ...
    
    # 7. Бизнес-логика
    def _ping_host_cmd(self): ...
```

**Итого**: MainWindow имеет **7 ответственностей** вместо одной!

---

### 3. ❌ **Tight Coupling (Сильная связанность)**

**Приоритет**: 🔴 **ВЫСОКИЙ**

#### Проблема: Менеджеры знают слишком много друг о друге

```python
# main_window.py, строка 196-200
self._theme_manager.set_ui_components(
    self._dashboard_frame, self._dashboard_labels,
    self._toolbar_layout, self._filters_layout,
    refresh_callback=lambda: self._dashboard_manager.force_refresh()  # ❌
)
```

**Граф зависимостей:**

```
MainWindow
   ├──> ThemeManager ──┐
   │                   │
   └──> DashboardManager <──┘  (через callback)
        ↑
        └── MainWindow вызывает force_refresh()
```

**Проблема**: Циклическая зависимость через callback!

---

### 4. ❌ **God Object Anti-pattern**

**Приоритет**: 🔴 **ВЫСОКИЙ**

#### MainWindow - это "Божественный объект"

**Признаки:**
- ✅ 661 строка кода (слишком много!)
- ✅ 35 методов
- ✅ Знает обо всех компонентах системы
- ✅ Координирует все взаимодействия
- ✅ Хранит огромное количество состояния

```python
class MainWindow:
    def __init__(self):
        # 20+ полей!
        self._storage = ...
        self._config = ...
        self._hosts = ...
        self._hosts_mutex = ...
        self._groups = ...
        self._hosts_map = ...
        self._table = ...
        self._table_model = ...
        self._search_edit = ...
        self._group_filter = ...
        self._status_filter = ...
        self._reset_filters_btn = ...
        self._toolbar_layout = ...
        self._filters_layout = ...
        self._dashboard_frame = ...
        self._dashboard_labels = ...
        self._filter_manager = ...
        self._theme_manager = ...
        self._dashboard_manager = ...
        self._export_import_manager = ...
        self._is_scanning = ...
        self._last_scan_time = ...
        self._needs_save = ...
        self._monitor_thread = ...
        self._save_timer = ...
        # ... и еще!
```

---

### 5. ❌ **Отсутствие слоя абстракции (Repository Pattern)**

**Приоритет**: 🟡 **СРЕДНИЙ**

#### Проблема: Прямая работа с файлами

```python
# storage.py
class StorageManager:
    def load_hosts(self) -> List[Host]:
        # Напрямую работает с JSON файлами
        with open(self._hosts_file, 'r') as f:
            data = json.load(f)
```

**Что не так:**
- ❌ Нельзя легко сменить хранилище на БД
- ❌ Нет единого интерфейса для работы с данными
- ❌ Тестирование требует реальных файлов

**Правильная архитектура:**

```
Application Layer
   ↓
Repository Interface (абстракция)
   ↓
JsonRepository | DatabaseRepository | CloudRepository
```

---

### 6. ❌ **Нет Event Bus / Mediator Pattern**

**Приоритет**: 🟡 **СРЕДНИЙ**

#### Проблема: Компоненты напрямую вызывают друг друга

```python
# main_window.py
def _on_status_updated(self, ...):
    # MainWindow напрямую вызывает DashboardManager
    self._dashboard_manager.update_status_transition(old_status, status)
    # И обновляет таблицу
    self._table_model.update_host_status(...)
```

**Правильный подход: Event Bus**

```python
# Компоненты публикуют события
event_bus.publish("host_status_changed", {
    "host_id": host_id,
    "old_status": old_status,
    "new_status": new_status
})

# Подписчики реагируют
dashboard_manager.subscribe("host_status_changed", on_status_changed)
table_model.subscribe("host_status_changed", on_status_changed)
```

**Преимущества:**
- ✅ Loose coupling (слабая связанность)
- ✅ Компоненты не знают друг о друге
- ✅ Легко добавлять новых подписчиков

---

### 7. ❌ **Смешивание уровней абстракции**

**Приоритет**: 🟡 **СРЕДНИЙ**

#### Проблема: MainWindow работает на разных уровнях

```python
class MainWindow:
    # Высокий уровень - координация
    def _init_managers(self): ...
    
    # Средний уровень - бизнес-логика
    def _modify_hosts_safely(self): ...
    
    # Низкий уровень - детали UI
    def _on_column_resized(self, index, old_size, new_size): ...
    def _ping_host_cmd(self, row): ...  # Запуск CMD!
```

**Правильно:**
- **Presentation Layer** (UI): MainWindow
- **Application Layer** (координация): ApplicationService
- **Domain Layer** (логика): HostService, ConfigService
- **Infrastructure Layer** (детали): StorageManager, PingService

---

### 8. ❌ **Отсутствие фасада для UI компонентов**

**Приоритет**: 🟢 **НИЗКИЙ**

#### Проблема: MainWindow создает UI напрямую

```python
def _init_ui(self):
    # Создание множества виджетов
    self._dashboard_frame, self._dashboard_labels = UIComponents.create_dashboard(theme)
    self._toolbar_layout = UIComponents.create_toolbar(self, theme)
    filter_result = UIComponents.create_filters(...)
    self._search_edit = filter_result[1]  # ❌ Магический индекс!
    self._group_filter = filter_result[2]
    # ...
```

**Решение: UI Facade**

```python
class MainWindowUI:
    """Фасад для управления UI компонентами"""
    def __init__(self, parent, theme):
        self._create_components(parent, theme)
    
    @property
    def search_edit(self): return self._search_edit
    
    @property
    def table(self): return self._table
```

---

### 9. ❌ **Нет разделения на слои (Layered Architecture)**

**Приоритет**: 🔴 **ВЫСОКИЙ**

#### Текущая структура (плоская):

```
main_window.py
filter_manager.py
theme_manager.py
storage.py
models.py
services.py
```

#### Правильная структура (слои):

```
src/
├── presentation/          # UI Layer
│   ├── windows/
│   │   └── main_window.py
│   └── managers/
│       ├── filter_manager.py
│       └── theme_manager.py
├── application/           # Application Layer
│   └── services/
│       ├── host_service.py
│       └── config_service.py
├── domain/                # Domain Layer
│   ├── models/
│   │   └── host.py
│   └── repositories/
│       └── host_repository.py (интерфейс)
└── infrastructure/        # Infrastructure Layer
    ├── persistence/
    │   ├── json_repository.py
    │   └── db_repository.py
    └── network/
        └── ping_service.py
```

---

### 10. ❌ **Circular Dependencies (потенциальные)**

**Приоритет**: 🟡 **СРЕДНИЙ**

#### Проблема в импортах:

```python
# models.py
from constants import SVG_ONLINE, SVG_OFFLINE  # ✅ Исправлено

# Потенциальная проблема:
# main_window.py → theme_manager.py → main_window (через QMainWindow)
```

**Граф импортов:**
```
main_window ──> filter_manager
     │             │
     └──> theme_manager
              │
              └──> QMainWindow (от main_window)
```

---

## 📊 Сводная таблица архитектурных проблем

| № | Проблема | Нарушенный принцип | Приоритет | Сложность исправления |
|---|----------|-------------------|-----------|----------------------|
| 1 | Нарушение DIP | SOLID (D) | 🔴 Критический | Высокая |
| 2 | Нарушение SRP | SOLID (S) | 🔴 Высокий | Средняя |
| 3 | Tight Coupling | Low Coupling | 🔴 Высокий | Высокая |
| 4 | God Object | Single Responsibility | 🔴 Высокий | Высокая |
| 5 | Нет Repository | Repository Pattern | 🟡 Средний | Средняя |
| 6 | Нет Event Bus | Mediator Pattern | 🟡 Средний | Средняя |
| 7 | Смешанные уровни | Layered Architecture | 🟡 Средний | Высокая |
| 8 | Нет UI Facade | Facade Pattern | 🟢 Низкий | Низкая |
| 9 | Плоская структура | Layered Architecture | 🔴 Высокий | Высокая |
| 10 | Circular Dependencies | - | 🟡 Средний | Низкая |

---

## 🎯 Решения архитектурных проблем

### Решение 1: Dependency Injection Container

```python
# di_container.py
class DIContainer:
    """Контейнер для Dependency Injection"""
    
    def __init__(self):
        self._services = {}
    
    def register(self, interface, implementation):
        """Регистрация сервиса"""
        self._services[interface] = implementation
    
    def resolve(self, interface):
        """Получение сервиса"""
        return self._services.get(interface)

# Использование
container = DIContainer()
container.register(IStorageRepository, JsonStorageRepository())
container.register(IPingService, PingService())

# В MainWindow
class MainWindow:
    def __init__(self, container: DIContainer):
        self._storage = container.resolve(IStorageRepository)
        self._ping_service = container.resolve(IPingService)
```

**Преимущества:**
- ✅ Легко подменить реализацию
- ✅ Упрощает тестирование
- ✅ Соблюдение DIP

---

### Решение 2: Repository Pattern

```python
# domain/repositories/host_repository.py
from abc import ABC, abstractmethod

class IHostRepository(ABC):
    """Интерфейс репозитория хостов"""
    
    @abstractmethod
    def get_all(self) -> List[Host]:
        pass
    
    @abstractmethod
    def get_by_id(self, host_id: str) -> Optional[Host]:
        pass
    
    @abstractmethod
    def save(self, host: Host) -> bool:
        pass
    
    @abstractmethod
    def delete(self, host_id: str) -> bool:
        pass

# infrastructure/persistence/json_host_repository.py
class JsonHostRepository(IHostRepository):
    """Реализация через JSON файлы"""
    
    def get_all(self) -> List[Host]:
        # Работа с файлами
        ...

# infrastructure/persistence/sqlite_host_repository.py
class SqliteHostRepository(IHostRepository):
    """Реализация через SQLite"""
    
    def get_all(self) -> List[Host]:
        # Работа с БД
        ...
```

---

### Решение 3: Event Bus (Mediator)

```python
# event_bus.py
from typing import Callable, Dict, List

class EventBus:
    """Шина событий для слабой связанности компонентов"""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event_name: str, handler: Callable):
        """Подписка на событие"""
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(handler)
    
    def publish(self, event_name: str, data: dict):
        """Публикация события"""
        if event_name in self._subscribers:
            for handler in self._subscribers[event_name]:
                handler(data)

# Использование
event_bus = EventBus()

# DashboardManager подписывается
event_bus.subscribe("host_status_changed", 
                   dashboard_manager.on_status_changed)

# MainWindow публикует
event_bus.publish("host_status_changed", {
    "host_id": "123",
    "old_status": "ONLINE",
    "new_status": "OFFLINE"
})
```

---

### Решение 4: Application Service Layer

```python
# application/services/host_service.py
class HostService:
    """Сервис для работы с хостами"""
    
    def __init__(self, repository: IHostRepository, event_bus: EventBus):
        self._repository = repository
        self._event_bus = event_bus
    
    def update_host_status(self, host_id: str, new_status: str):
        """Обновление статуса хоста"""
        host = self._repository.get_by_id(host_id)
        if not host:
            return
        
        old_status = host.status
        host.status = new_status
        
        if self._repository.save(host):
            # Публикуем событие
            self._event_bus.publish("host_status_changed", {
                "host_id": host_id,
                "old_status": old_status,
                "new_status": new_status
            })
    
    def get_all_hosts(self) -> List[Host]:
        return self._repository.get_all()
```

---

### Решение 5: Разделение MainWindow

```python
# Вместо одного God Object создаем несколько классов:

# 1. MainWindow (координация)
class MainWindow(QMainWindow):
    def __init__(self, services: ApplicationServices):
        self._services = services
        self._ui = MainWindowUI(self)
        self._setup_event_handlers()

# 2. MainWindowUI (управление UI)
class MainWindowUI:
    def create_ui(self, parent):
        # Создание всех UI компонентов
        pass

# 3. ContextMenuManager (контекстные меню)
class ContextMenuManager:
    def show_host_menu(self, position):
        # Меню для хоста
        pass

# 4. TableSettingsManager (настройки таблицы)
class TableSettingsManager:
    def save_column_widths(self):
        # Сохранение настроек
        pass
```

---

## 🏆 Целевая архитектура (Clean Architecture)

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│  (UI, Controllers, ViewModels)          │
│  - MainWindow                           │
│  - FilterManager, ThemeManager          │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         Application Layer               │
│  (Use Cases, Services)                  │
│  - HostService                          │
│  - ConfigService                        │
│  - EventBus                             │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         Domain Layer                    │
│  (Business Logic, Entities)             │
│  - Host, AppConfig                      │
│  - IHostRepository (interface)          │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         Infrastructure Layer            │
│  (External Services, Persistence)       │
│  - JsonHostRepository                   │
│  - PingService                          │
│  - NotificationService                  │
└─────────────────────────────────────────┘
```

---

## 📈 План миграции на новую архитектуру

### Этап 1: Dependency Injection (2-3 часа)
- [ ] Создать DIContainer
- [ ] Создать интерфейсы (IStorage, IPingService)
- [ ] Переписать MainWindow на DI

### Этап 2: Repository Pattern (3-4 часа)
- [ ] Создать IHostRepository
- [ ] Реализовать JsonHostRepository
- [ ] Мигрировать StorageManager

### Этап 3: Event Bus (2-3 часа)
- [ ] Создать EventBus
- [ ] Заменить прямые вызовы на события
- [ ] Подписать менеджеры на события

### Этап 4: Разделение MainWindow (4-5 часов)
- [ ] Создать ApplicationServices
- [ ] Вынести ContextMenuManager
- [ ] Вынести TableSettingsManager
- [ ] Создать MainWindowUI

### Этап 5: Слоистая архитектура (5-6 часов)
- [ ] Реорганизовать файлы по слоям
- [ ] Создать Application Services
- [ ] Выделить Domain Layer
- [ ] Переместить Infrastructure

**Общее время**: ~20 часов

---

## 📝 Заключение

### Текущее состояние:
- ❌ Сильная связанность (Tight Coupling)
- ❌ God Object (MainWindow)
- ❌ Прямые зависимости от реализаций
- ❌ Плоская структура
- ❌ Смешанные уровни абстракции

### После рефакторинга:
- ✅ Слабая связанность (Loose Coupling)
- ✅ Single Responsibility для всех классов
- ✅ Dependency Injection
- ✅ Clean Architecture (слои)
- ✅ Легко тестируется
- ✅ Легко расширяется

**Оценка текущей архитектуры**: 4/10  
**Оценка после исправлений**: 8/10

Архитектура требует серьезного рефакторинга для соответствия best practices! 🏗️
