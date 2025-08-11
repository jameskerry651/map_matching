## 在docker中部署map_matching

### 下载pbf文件
在以下链接中下载pbf文件，将pbf文件放入docker_volume目录下

` https://download.openstreetmap.fr/extracts/asia/china/ `

### 启动容器
从docker_volume启动终端，执行以下命令启动容器，注意替换对应的pbf文件

`docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-extract -p /opt/car.lua /data/sichuan-latest.osm.pbf || echo "osrm-extract failed"`

`-v "${PWD}:/data"`
这是用来挂载一个卷（volume）的标志。卷用于在宿主机（你的电脑）和Docker容器之间共享文件。[3]
`"${PWD}"`: 这是一个shell变量，代表“Present Working Directory”，即你当前所在的终端目录。
:: 这是分隔符，左边是宿主机路径，右边是容器内路径。
/data: 这是容器内部的一个目录路径。
作用: 这条设置将你当前所在的文件夹（${PWD}）映射到容器内的/data目录。这样，容器就可以访问你当前文件夹里的文件，并且在容器的/data目录中创建的文件也会出现在你宿主机的当前文件夹中。

osrm-extract
这是OSRM工具集中的一个程序，它的作用是从原始的OSM数据（.osm.pbf格式）中提取路网信息，并将其转换为OSRM可以进行快速计算的图结构。[6][7] 这是处理数据的第一步。

`-p /opt/car.lua` 这个标志用来指定一个“配置文件”（profile）
配置文件是使用Lua语言编写的脚本，它定义了路由的规则。

`/opt/car.lua` 是OSRM内置的针对汽车的配置文件。它包含了汽车可以行驶的道路类型、速度限制、转弯惩罚等规则。[8][9] OSRM也提供foot.lua（步行）和bicycle.lua（自行车）等其他配置文件。[8]

`/data/sichuan-latest.osm.pbf`
这是osrm-extract命令要处理的输入文件。
由于前面设置了卷挂载 (-v "${PWD}:/data")，这个路径指向你宿主机当前目录下的pbf文件。

### 构建索引
执行以下命令构建索引

`docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-partition /data/sichuan-latest.osrm || echo "osrm-partition failed"`

`docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-customize /data/sichuan-latest.osrm || echo "osrm-customize failed"`

第一条命令：为了实现极快的路径计算（通常在几毫秒内），OSRM 使用了一种名为“可收缩层级 (Contraction Hierarchies, CH)”的算法。osrm-partition 就是实现这个算法的准备步骤。
它会将路网图分割成多个层级和区域（分区）。可以把它想象成给地图建立一个“高速公路网络”的索引。当你查询一条长途路线时，OSRM 会先利用这个分区信息快速跳到“高速公路”层级进行计算，而不是逐一检查每一条小路，从而极大地提升了查询速度。
简单来说，osrm-partition 的工作是为地图数据建立一个加速索引，以便后续能够进行超快速的路径规划。
执行成功后，它会更新和生成一些新的 .osrm.* 文件（例如 .osrm.partition），这些文件包含了分区信息。

第二条命令：osrm-customize 是 osrm-partition 的后续步骤，它会根据分区信息对地图进行优化。osrm-partition 建立的“可收缩层级”虽然速度极快，但有一个缺点：它是静态的。一旦层级建立，路网的“成本”（例如，通过一条路所需的时间）就被固定了。
但在现实世界中，路况是动态变化的（例如交通拥堵）。osrm-customize 的作用就是对数据进行进一步处理，使其能够利用另一种名为“多级 Dijkstra (Multi-Level Dijkstra, MLD)”的算法。
MLD 算法允许在不破坏预处理数据结构的情况下，快速更新道路的权重（通行时间）。这使得 OSRM 可以在不重新运行整个预处理流程的情况下，集成实时交通数据。
简单来说，osrm-customize 的工作是让预处理好的地图数据变得“可定制”，使其能够快速适应交通拥堵等动态变化。
执行成功后，它会再次更新和生成一系列 .osrm.* 文件（例如 .osrm.cells, .osrm.customize），为最终的路由引擎做好准备。

### 启动服务器
执行
`docker run -t -i -p 5000:5000 -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-routed --algorithm mld /data/sichuan-latest.osrm`

这是启动 OSRM 路由引擎的命令。
-t -i 这两个标志是用来创建一个交互式的容器会话的。
-p 5000:5000 这是端口映射，将容器内的 5000 端口映射到宿主机的 5000 端口。这意味着你可以通过 http://localhost:5000 来访问 OSRM 服务。
-v "${PWD}:/data" 这是挂载卷的设置，将当前目录挂载到容器内的 /data 目录。
ghcr.io/project-osrm/osrm-backend 这是 OSRM 路由引擎的 Docker 镜像。
osrm-routed 这是镜像中的一个程序，它是 OSRM 路由引擎的主程序。
--algorithm mld 这是指定使用 MLD 算法进行路由计算。
