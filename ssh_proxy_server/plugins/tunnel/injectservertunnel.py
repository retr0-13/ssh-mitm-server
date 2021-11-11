import logging
from socket import socket
from typing import TYPE_CHECKING, Optional, Tuple, Text, Union

import paramiko
from typeguard import typechecked

import ssh_proxy_server
from ssh_proxy_server.forwarders.tunnel import ServerTunnelForwarder, TunnelForwarder
from ssh_proxy_server.plugins.session.tcpserver import TCPServerThread

if TYPE_CHECKING:
    from ssh_proxy_server.interfaces.server import ServerInterface
    from ssh_proxy_server.session import Session

class InjectableServerTunnelForwarder(ServerTunnelForwarder):
    """For each server port forwarding request open a local port to inject traffic into the port-forward

    The Handler is still the same as the ServerTunnelForwarder, only a tcp server is added

    """

    @classmethod
    @typechecked
    def parser_arguments(cls) -> None:
        plugin_group = cls.parser().add_argument_group(cls.__name__)
        plugin_group.add_argument(
            '--tunnel-server-net',
            dest='server_tunnel_net',
            default='127.0.0.1',
            help='local address/interface where injector sessions are served'
        )

    @typechecked
    def __init__(
        self,
        session: 'ssh_proxy_server.session.Session',
        server_interface: 'ssh_proxy_server.interfaces.server.ServerInterface',
        destination: Optional[Tuple[str, int]]
    ) -> None:
        super().__init__(session, server_interface, destination)
        self.tcpserver = TCPServerThread(
            self.serve,
            network=self.args.server_tunnel_net,
            run_status=self.session.running
        )
        logging.info(
            f"created server tunnel injector for host {self.tcpserver.network} on port {self.tcpserver.port} to destination {self.destination}"
        )
        self.tcpserver.start()

    @typechecked
    def serve(self, client: Union[socket, paramiko.Channel], addr: Tuple[Text, int]) -> None:
        try:
            f = TunnelForwarder(
                self.session.transport.open_channel("forwarded-tcpip", self.destination, addr),
                client
            )
            self.server_interface.forwarders.append(f)
        except (paramiko.SSHException, OSError):
            logging.warning("injector connection suffered an unexpected error")
            self.tcpserver.close()
