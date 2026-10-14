# Docker-окружение flight_rpi для Raspberry Pi 5

Дата подготовки: 13 октября 2026 года.

Комплект предназначен для существующего Git-репозитория `~/flight_rpi` на Raspberry Pi 5 с 64-битной Raspberry Pi OS. Все конфигурационные файлы помещаются в корень этого репозитория. Основная папка внутри контейнера — `/workspaces/flight_rpi`.

## Что входит

| Компонент | Содержание |
|---|---|
| ОС контейнера | Официальный `ros:jazzy-ros-base-noble`, Ubuntu 24.04, ARM64 |
| ROS | Jazzy, инструменты colcon/rosdep/vcstool, rosbag2 и MCAP |
| MAVLink | MAVROS, mavros_extras, pymavlink 2.4.49, MAVProxy 1.8.74 |
| Географические преобразования | GeographicLib для C++ и Python, PyProj, геоид EGM96-5 |
| Зависимости VINS | Ceres 2.1.0, Eigen, OpenCV, glog, gflags, Boost, BLAS/LAPACK |
| Работа с изображениями | cv_bridge, image_transport, image_proc, compressed transports |
| Драйверы камер | usb_cam и v4l2_camera для совместимых V4L2-устройств |
| Разработка | tmux, zsh, autosuggestions, syntax highlighting, bash, Git, nano, vim, CMake, Ninja, gdb |
| Диагностика | usbutils, v4l-utils, pySerial, htop, lsof, ripgrep, сетевые утилиты |
| Визуализация | Foxglove Bridge отдельным сервисом Compose |

Собственные ROS 2 пакеты и закреплённый ROS 2 порт VINS нужно помещать в `ros2_ws/src/`. Их сборка выполняется отдельно. Исходный ROS 1 VINS с catkin не становится ROS 2 пакетом за счёт смены контейнера.

Для Ceres выбран CPU-режим, EigenSparse и LAPACK. Бэкенд SuiteSparse отключён: старую версию Ceres не привязываем к меняющемуся API SuiteSparse из Ubuntu 24.04. Библиотеки SuiteSparse присутствуют для других компонентов. Ceres установлен отдельно в `/opt/ceres/2.1.0`; параметр `Ceres_DIR` указывает на него. Эта версия сохраняет API `LocalParameterization`, удалённый в Ceres 2.2. Если конкретный порт явно требует бэкенд SuiteSparse, его нужно согласовать с используемой версией библиотеки перед изменением флага.

Python-библиотеки из pip установлены в `/opt/flight-venv` с доступом к системным ROS-пакетам. Команда `colcon` запускается тем же Python, чтобы Python-пакеты проекта получили правильный интерпретатор. Системный Python Ubuntu не изменяется установкой pip.

## Файлы

| Файл | Ответственность |
|---|---|
| `Dockerfile` | Зависимости, пользователь контейнера, Ceres, GeographicLib, инструменты |
| `compose.yaml` | Сервисы `dev` и `foxglove`, устройства, сеть, постоянные данные |
| `.devcontainer/devcontainer.json` | VS Code, каталог проекта, терминалы zsh/bash/tmux |
| `.env.example` | Образец параметров хоста, DDS и порта Foxglove |
| `scripts/configure-host.sh` | Создание локального `.env`, каталогов workspace и правил `.gitignore` |
| `scripts/install-docker.sh` | Docker Engine и Compose из официального репозитория Debian |
| `compose.extra.example.yaml` | Пример дополнительного bind mount |
| `docker/99-flight-usb.rules` | Необязательные права на raw USB и hidraw для группы plugdev |
| `docker/verify-environment.sh` | Проверка импортов, ROS-пакетов, данных GeographicLib и сборки с Ceres |

Архив распаковывается непосредственно в существующий `~/flight_rpi`. Команда `unzip -n` сохраняет файлы, уже присутствующие под такими же именами. Если конфигурационные файлы с этими именами уже существуют, нужно сравнить их с комплектом и объединить изменения перед сборкой.

## 1. Перенос файлов

На ноутбуке отправь скачанный архив на плату, заменив `IP_ПЛАТЫ` фактическим адресом:

```bash
scp ~/Downloads/flight_rpi_docker_setup.zip rpi-test-tiit@IP_ПЛАТЫ:~/
```

Команда копирует архив в домашний каталог пользователя платы. Ожидается успешное завершение передачи.

На Raspberry Pi установи распаковщик:

```bash
sudo apt update && sudo apt install -y unzip
```

Команда обновляет список пакетов и устанавливает `unzip`.

```bash
cd ~/flight_rpi
unzip -n ~/flight_rpi_docker_setup.zip
```

Первая команда выбирает существующий репозиторий, вторая извлекает файлы комплекта в его корень. Ожидается появление `Dockerfile`, `compose.yaml`, `.devcontainer/`, `docker/` и `scripts/`.

## 2. Docker на хосте

Выполняется на Raspberry Pi:

```bash
sudo bash scripts/install-docker.sh
```

Скрипт проверяет ARM64 и Debian Bookworm/Trixie, устанавливает Docker Engine, Buildx и Compose plugin, включает службу Docker и добавляет пользователя, вызвавшего sudo, в группу `docker`. При уже установленном Docker с Compose установка пакетов пропускается. Конфликтующие пакеты автоматически не удаляются.

Группа `docker` даёт возможность управлять привилегированным Docker daemon; её членство следует выдавать пользователю разработки. После выполнения закрой старое SSH/Remote SSH-подключение и подключись заново: новое членство в группе действует в новых сеансах.

```bash
docker version
docker compose version
docker run --rm hello-world
```

Первая команда должна показать Client и Server без ошибки доступа к socket. Вторая проверяет Compose plugin. Третья скачивает и запускает короткий тестовый контейнер, который выводит сообщение об успешной работе Docker.

## 3. Локальная конфигурация и сборка

Под обычным пользователем, без sudo:

```bash
bash scripts/configure-host.sh
```

Скрипт создаёт `.env` с фактическими UID/GID и числовыми группами устройств хоста, создаёт `ros2_ws/src` и `config`, добавляет необходимые правила в существующий `.gitignore`. Существующий `.env` сохраняется. Если группы `plugdev` нет, скрипт создаёт её через sudo. `.env` содержит параметры конкретной платы и игнорируется Git; `.env.example` включается в репозиторий.

```bash
docker compose config --quiet
```

Проверяет корректность Compose и подстановок из `.env`. Ожидается завершение без ошибок и без вывода.

```bash
docker compose build
```

Собирает ARM64-образ. Во время первой сборки скачиваются пакеты, Python-библиотеки, Ceres и модель геоида. Сборка Ceres ограничена двумя параллельными заданиями через `BUILD_JOBS=2`. Если памяти недостаточно, установи `BUILD_JOBS=1` в `.env` и повтори сборку.

```bash
docker compose up -d
docker compose ps
```

Первая команда запускает сервисы в фоне, вторая показывает состояние. Ожидаются работающие `flight_rpi_dev` и `flight_rpi_foxglove`.

## 4. Работа через VS Code

1. Установи на ноутбуке расширения Remote - SSH и Dev Containers.
2. Подключись к Raspberry Pi через Remote - SSH.
3. Открой существующую папку `~/flight_rpi`.
4. Выполни `Dev Containers: Reopen in Container` через палитру команд.

VS Code подключается к сервису `dev`. Рабочий каталог — `/workspaces/flight_rpi`. Серверная часть VS Code устанавливается расширением автоматически. После закрытия VS Code сервисы продолжают работать: `shutdownAction` задан как `none`.

Внутри VS Code новый терминал использует zsh. Доступны профили bash и `tmux (flight)`. Шрифт и цветовая палитра задаются на ноутбуке; конфигурация оболочки находится в образе. Реальный `TERM` сохраняется, дополнительные определения терминалов установлены через `ncurses-term`.

Файлы проекта являются одним bind mount: изменения внутри контейнера сразу появляются в `~/flight_rpi` на хосте. UID/GID пользователя `flight` совпадают с UID/GID пользователя хоста, поэтому файлы не получают владельца root при обычной работе.

Git можно использовать в терминале VS Code. Каталог `.git` доступен через тот же mount. Для HTTPS-авторизации Dev Containers поддерживает обмен credentials с окружением VS Code. Если Git сообщает об отсутствии имени автора, проверь `git config --get user.name` и `git config --get user.email`: команды должны вывести имя и email. Настройки автора и авторизация GitHub являются отдельными механизмами.

## 5. Tmux

Сервис `dev` создаёт сессию `flight` с окнами `shell`, `ros` и `devices`. Подключение с хоста:

```bash
docker compose exec dev tmux attach-session -t flight
```

Команда присоединяет терминал к существующей сессии. Ожидаются три окна в нижней строке tmux.

| Клавиши | Действие |
|---|---|
| `Ctrl+B`, затем `0/1/2` | Переключить окно |
| `Ctrl+B`, затем `c` | Создать окно |
| `Ctrl+B`, затем `d` | Отсоединиться с сохранением процессов |

Tmux-сессия переживает разрыв SSH, пока работает контейнер. При пересоздании контейнера сессия и её процессы завершаются; история оболочки сохраняется в отдельном Docker volume. Автозапуск навигационных узлов позднее нужно описать в ROS launch/команде сервиса.

## 6. Устройства USB, UART и камеры

`/dev` хоста подключён в `/dev` контейнера. `/run/udev` доступен для чтения. Правило `c *:* rwm` разрешает обращаться к символьным устройствам с любыми major/minor, в том числе к устройствам, появившимся после запуска контейнера. Режим `privileged` не включён; блочные устройства не получают разрешение на чтение/запись этим правилом.

Это широкий доступ для среды разработки, включая другие символьные устройства хоста. После определения реальных датчиков целесообразно сузить правила до нужных классов устройств. Каталог `/dev` включает также псевдотерминалы хоста; эту конфигурацию следует использовать как доверенную среду разработки на плате.

| Тип | Обычные пути |
|---|---|
| USB–UART | `/dev/ttyUSB0`, `/dev/ttyUSB1` |
| USB CDC/ACM | `/dev/ttyACM0` |
| UART Raspberry Pi | `/dev/ttyAMA*`, `/dev/serial0`, в зависимости от настройки платы |
| Raw USB/libusb | `/dev/bus/usb/...` |
| V4L2-камера | `/dev/video*` |
| Стабильное имя USB serial | `/dev/serial/by-id/...`, если устройство предоставляет идентификатор |

Проброс устройства сохраняет его обычные Linux-права. Пользователь контейнера получает дополнительные числовые группы dialout/video/plugdev/input хоста. Если узел принадлежит другой группе или разрешён только root, потребуется соответствующее правило udev либо запуск конкретной диагностической команды через sudo внутри контейнера.

Проверки внутри контейнера:

```bash
lsusb
python3 -m serial.tools.list_ports -v
v4l2-ctl --list-devices
```

Команды показывают USB-устройства, последовательные порты и V4L2-камеры. Отсутствие устройства означает, что нужно проверить подключение, драйвер или настройку интерфейса на хосте. Контейнер не включает отключённый UART и не устанавливает драйвер в ядро Raspberry Pi OS.

Переподключение USB создаёт новый узел устройства, видимый через mount `/dev`. Приложение, потерявшее открытый порт, должно уметь открыть его заново либо быть перезапущено. Видимость устройства и восстановление связи приложением проверяются отдельно.

Для разработки с raw USB/libusb/hidraw можно установить готовое правило на хосте:

```bash
sudo install -m 0644 docker/99-flight-usb.rules /etc/udev/rules.d/99-flight-usb.rules
sudo udevadm control --reload-rules
```

Первая команда предоставляет группе `plugdev` чтение/запись raw USB и hidraw. Вторая перечитывает правила. Новые права применяются при следующем подключении соответствующего устройства. Последовательные порты и V4L2-узлы продолжают использовать свои группы. Это необязательная настройка для устройств, которым недостаточно стандартных прав.

Камеры CSI/libcamera требуют отдельной проверки модели, драйверов и совместимости libcamera с хостом. Наличие `/dev/video*` и двух ROS-драйверов не гарантирует поддержку любой камеры Raspberry Pi.

## 7. Сеть и Foxglove

Оба сервиса используют `network_mode: host`, то есть сетевой namespace Raspberry Pi. Публикация через `ports:` в таком режиме не применяется. Сервис получает доступ к TCP/UDP-портам хоста, когда его приложение создаёт слушающий socket.

| Порт | Назначение |
|---|---|
| TCP 8765 | Foxglove Bridge, запущен сервисом `foxglove` |
| UDP 14540 | Возможная конфигурация MAVLink/PX4; слушатель появляется после запуска MAVROS/другого процесса |
| UDP 14550 | Возможная конфигурация MAVLink/GCS; слушатель появляется после запуска соответствующего процесса |

`EXPOSE` в Dockerfile содержит метаданные этих портов. Для 14540/14550 не запускается фиктивный сервер: направление и адреса задаются в `fcu_url` и конфигурации MAVLink.

В Foxglove выбери Foxglove WebSocket и адрес `ws://IP_ПЛАТЫ:8765`. При использовании туннеля VS Code можно подключаться к `ws://localhost:8765`, если на ноутбуке этот порт свободен. Если VS Code выбрал другой локальный порт, используй его из панели Ports. Межсетевой экран и изоляция клиентов Wi-Fi должны разрешать прямое соединение с платой.

```bash
docker compose logs --tail 50 foxglove
```

Показывает журнал моста. Ожидается запуск WebSocket-сервера без ошибок привязки порта.

```bash
docker compose exec dev python3 -c 'import socket; socket.create_connection(("127.0.0.1", 8765), timeout=5).close(); print("TCP 8765 available")'
```

Проверяет доступность TCP-слушателя. Ожидается `TCP 8765 available`. Это проверка сетевого подключения; фактические ROS-топики проверяются в Foxglove.

Порт меняется в `.env` через `FOXGLOVE_PORT`. При его изменении также обнови `forwardPorts`/`portsAttributes` в Dev Container. Пересоздай сервисы командой `docker compose up -d`: она применяет новые параметры сервиса.

`ROS_DOMAIN_ID=42` выбран как отдельный DDS-домен проекта. Для обмена с ROS-узлами на другой машине они должны использовать тот же domain ID и совместимую сеть. Сеть хоста упрощает UDP/multicast, но не отменяет ограничения маршрутизации и Wi-Fi.

## 8. Проверка окружения

На хосте:

```bash
docker compose exec dev bash -lc 'flight-verify'
```

Проверяет ARM64, Python-импорты, ROS-пакеты, GeographicLib и компиляцию/линковку маленькой программы с Ceres 2.1 и `LocalParameterization`. Ожидается финальная строка `Environment checks passed.`

В контейнере проверь общий каталог:

```bash
pwd
id
```

Первая команда должна показать `/workspaces/flight_rpi`; вторая — UID/GID пользователя `flight`, соответствующие хосту. Отредактируй небольшой файл в VS Code и проверь его наличие на хосте: это подтверждает общий bind mount без создания временного тестового файла в репозитории.

## 9. Дополнительные каталоги

Пример для каталога записей на хосте:

```bash
mkdir -p ~/flight_data
printf '\nFLIGHT_DATA_DIR=%s\n' "$HOME/flight_data" >> .env
```

Первая команда создаёт каталог. Вторая добавляет его абсолютный путь в локальные настройки. Выполни добавление параметра один раз; при последующих изменениях редактируй существующее значение в `.env`.

```bash
docker compose -f compose.yaml -f compose.extra.example.yaml config --quiet
docker compose -f compose.yaml -f compose.extra.example.yaml up -d
```

Первая команда проверяет объединённую конфигурацию, вторая применяет дополнительный mount `~/flight_data` → `/data` в сервисе `dev`.

Чтобы Dev Containers использовал этот же дополнительный файл, замени значение `dockerComposeFile` на:

```json
["../compose.yaml", "../compose.extra.example.yaml"]
```

Затем выполни `Dev Containers: Rebuild Container`. Дополнительные папки задаются следующими элементами `volumes` по этому же образцу. Для чтения калибровок можно добавить `read_only: true`.

## 10. Работа с ROS-пакетами

После добавления нужного ROS 2 порта VINS и собственных пакетов в `ros2_ws/src`, выполняй в контейнере:

```bash
cd /workspaces/flight_rpi/ros2_ws
rosdep update
rosdep install --from-paths src --ignore-src --rosdistro jazzy -y --skip-keys "libceres-dev ceres-solver"
flight-build
```

Первая команда выбирает workspace. `rosdep update` обновляет пользовательский кэш правил зависимостей. `rosdep install` устанавливает зависимости из `package.xml`, сохраняя наш Ceres вместо системного `libceres-dev`. Количество и имена остальных skip-keys могут потребовать уточнения по выбранному порту. `flight-build` очищает переменные старого ROS overlay, подключает базовый Jazzy и Ceres 2.1, затем запускает colcon с последовательной сборкой пакетов и ограничением параллелизма CMake до двух заданий. При нехватке памяти используй `CMAKE_BUILD_PARALLEL_LEVEL=1 flight-build`.

Для использования новой сборки в уже открытом zsh:

```zsh
source install/setup.zsh
```

Команда добавляет собранные пакеты в окружение этого терминала. Новые терминалы автоматически подхватывают существующий `install/setup.zsh`. Для пересборки пользуйся `flight-build`: старый overlay автоматически исключается из окружения процесса сборки.

Для нового Python-зависимого пакета из pip редактируй `docker/python-requirements.txt` и пересобирай образ. Для системного или ROS-пакета редактируй `docker/apt-packages.txt`.

## 11. Управление и фиксация

| Команда на хосте | Назначение |
|---|---|
| `docker compose ps` | Состояние сервисов |
| `docker compose logs -f foxglove` | Непрерывный журнал Foxglove; Ctrl+C завершает просмотр |
| `docker compose exec dev zsh` | Новый интерактивный терминал внутри контейнера |
| `docker compose restart foxglove` | Перезапуск моста |
| `docker compose stop` | Остановка обоих сервисов |
| `docker compose up -d` | Возобновление сервисов |
| `docker compose up -d --build` | Пересборка при изменении Dockerfile и применение конфигурации |
| `docker compose down` | Удаление контейнеров; основной каталог и обычные named volumes сохраняются |

`restart: unless-stopped` возвращает контейнеры после перезагрузки платы, если их ранее явно не остановили. Docker должен быть включён как системная служба. Foxglove имеет собственный основной процесс и перезапускается отдельно. Сервис `dev` удерживается командой `sleep infinity`; падение программы в tmux не завершает контейнер и само по себе не вызывает Docker restart.

Журналы Docker ограничены тремя файлами по 10 MiB на сервис. Данные экспериментов сохраняй в host bind mount, чтобы пересоздание контейнера их не удалило.

В терминале VS Code:

```bash
git status --short
git diff
```

Первая команда перечисляет изменения, вторая показывает изменения уже отслеживаемых файлов. Новые Dockerfile/Compose нужно открыть и проверить отдельно либо посмотреть после добавления через `git diff --cached`.

```bash
git add Dockerfile compose.yaml compose.extra.example.yaml .devcontainer .dockerignore .env.example .gitignore.container .gitignore docker scripts DOCKER_SETUP_RU.md
git diff --cached
git commit -m "Add ROS 2 Jazzy ARM64 development container"
git push
```

`git add` выбирает файлы конфигурации, `git diff --cached` показывает точный будущий коммит, `git commit` фиксирует его локально, `git push` отправляет его в настроенную удалённую ветку. `.env` остаётся локальным.

## Проверки и ограничения комплекта

При подготовке проверены синтаксис shell-скриптов, YAML/JSON, подстановки и логика конфигурации, а также запуск генератора настроек на изолированной имитации хоста. Проверены пути исходных файлов, переносимость архива и отсутствие `.git`/локальных credentials.

Полная сборка образа, запуск Docker, проверка GPIO/USB/UART, скорости камеры и интеграция с Pixhawk выполняются на Raspberry Pi. В среде подготовки Docker daemon отсутствовал, поэтому комплект не объявляется собранным или аппаратно испытанным.

Для строгой повторяемости нужно закрепить digest базового образа, версии apt-пакетов и commit ROS 2 порта VINS. Сейчас базовый образ выбирается по фиксированному тегу дистрибутива, apt-пакеты — из его актуального репозитория. Фактически установленные версии сохраняются в `/opt/flight-build/apt-packages.tsv` и `/opt/flight-build/python-packages.txt`.

## Официальные источники

- [Официальные ROS Docker-образы и ARM64-теги](https://github.com/docker-library/official-images/blob/master/library/ros).
- [ROS 2 Jazzy: Ubuntu 24.04 и ARM64](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html).
- [Docker Engine: установка на Debian](https://docs.docker.com/engine/install/debian/#install-using-the-apt-repository).
- [Docker: bind mounts](https://docs.docker.com/engine/storage/bind-mounts/).
- [Docker: сеть хоста](https://docs.docker.com/engine/network/drivers/host/).
- [Docker: динамические устройства и cgroup rules](https://docs.docker.com/reference/cli/docker/container/run/#using-dynamically-created-devices---device-cgroup-rule).
- [Compose: devices и device_cgroup_rules](https://docs.docker.com/reference/compose-file/services/#device_cgroup_rules).
- [VS Code: удалённый Docker через Remote SSH](https://code.visualstudio.com/remote/advancedcontainers/develop-remote-host#_connect-using-the-remote-ssh-extension).
- [VS Code: пользователь контейнера и UID/GID](https://code.visualstudio.com/remote/advancedcontainers/add-nonroot-user).
- [VS Code: Git credentials в Dev Container](https://code.visualstudio.com/remote/advancedcontainers/sharing-git-credentials).
- [Foxglove Bridge: запуск и параметры](https://github.com/foxglove/foxglove-sdk/blob/main/ros/src/foxglove_bridge/README.md).
- [MAVROS: установка и GeographicLib](https://github.com/mavlink/mavros/blob/ros2/docs/installation.md).
- [Ceres: документация версии 2.1.0](https://ceres-solver.googlesource.com/ceres-solver/+/refs/tags/2.1.0/docs/source/installation.rst).
- [Ceres: изменения API](https://ceres-solver.readthedocs.io/latest/version_history.html).
- [Tmux: руководство](https://github.com/tmux/tmux/wiki/Getting-Started).
- [Zsh: редактор командной строки](https://zsh.sourceforge.io/Doc/Release/Zsh-Line-Editor.html).
- [Pymavlink 2.4.49](https://pypi.org/project/pymavlink/2.4.49/).
- [MAVProxy 1.8.74](https://pypi.org/project/MAVProxy/1.8.74/).
