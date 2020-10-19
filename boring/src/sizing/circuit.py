import openmdao.api as om


class Resistor(om.ExplicitComponent):
    """Computes flux across a resistor using Ohm's law."""

    def initialize(self):
        self.options.declare('R', default=1., desc='Thermal Resistance in m*k/W')

    def setup(self):
        self.add_input('T_in', units='K')
        self.add_input('T_out', units='K')
        self.add_output('q', units='W')

        self.declare_partials('q', 'T_in', method='fd')
        self.declare_partials('q', 'T_out', method='fd')

    def compute(self, inputs, outputs):
        deltaT = inputs['T_in'] - inputs['T_out']
        outputs['q'] = deltaT / self.options['R']

    def compute_partials(self, inputs, J):
        J['']

class Node(om.ImplicitComponent):
    """Computes temperature residual across a node based on incoming and outgoing flux."""

    def initialize(self):
        self.options.declare('n_in', default=1, types=int, desc='number of connections with + assumed in')
        self.options.declare('n_out', default=1, types=int, desc='number of current connections + assumed out')

    def setup(self):
        self.add_output('T', val=5., units='K')

        for i in range(self.options['n_in']):
            q_name = 'q_in:{}'.format(i)
            self.add_input(q_name, units='W')

        for i in range(self.options['n_out']):
            q_name = 'q_out:{}'.format(i)
            self.add_input(q_name, units='W')

    def setup_partials(self):
        #note: we don't declare any partials wrt `T` here,
        #      because the residual doesn't directly depend on it
        self.declare_partials('T', 'q*', method='fd')

    def apply_nonlinear(self, inputs, outputs, residuals):
        residuals['T'] = 0.
        for q_conn in range(self.options['n_in']):
            residuals['T'] += inputs['q_in:{}'.format(q_conn)]
        for q_conn in range(self.options['n_out']):
            residuals['T'] -= inputs['q_out:{}'.format(q_conn)]


class Circuit(om.Group):
    """ Thermal equivalent circuit """
    def setup(self):

        self.add_subsystem('n1', Node(n_in=1, n_out=2), promotes_inputs=[('q_in:0', 'q_in')])  # 2 out
        self.add_subsystem('n2', Node(n_in=1, n_out=2))  # 2 out
        self.add_subsystem('n3', Node(n_in=1, n_out=1))  # 1
        self.add_subsystem('n4', Node(n_in=1, n_out=1))  # 1
        self.add_subsystem('n5', Node(n_in=1, n_out=1))  # 1
        self.add_subsystem('n6', Node(n_in=1, n_out=1))  # 1
        self.add_subsystem('n7', Node(n_in=2, n_out=1))  # 2 in
        self.add_subsystem('n8', Node(n_in=2, n_out=1), promotes_inputs=[('q_out:0', 'q_out')])  # 2 in


        self.add_subsystem('Rwe', Resistor(R=10.), promotes_inputs=[('T_in', 'T_hot')]) # evaporator wall
        self.add_subsystem('Rwke', Resistor(R=10.)) # evaporator wick
        self.add_subsystem('Rinter_e', Resistor(R=10.))
        self.add_subsystem('Rv', Resistor(R=10.)) # vapor
        self.add_subsystem('Rwka', Resistor(R=10.)) # wick adiabatic
        self.add_subsystem('Rwa', Resistor(R=10.)) # wall adiabatic
        self.add_subsystem('Rinter_c', Resistor(R=10.)) #
        self.add_subsystem('Rwkc', Resistor(R=10.)) # condensor wick
        self.add_subsystem('Rwc', Resistor(R=10.), promotes_inputs=[('T_out', 'T_cold')]) #condensor wall

        # node 1 (q_in promoted, 'Rwe.T_in',  3 additional connections)
        self.connect('n1.T', ['Rwa.T_in']) # define temperature node as resitor inputs
        self.connect('Rwe.q', 'n1.q_out:0') # connect resistor flux to each node port
        self.connect('Rwa.q', 'n1.q_out:1')
        # node 2 (6 connections)
        self.connect('Rwe.q', 'n2.q_in:0')
        self.connect('n2.T', ['Rwke.T_in', 'Rwka.T_in','Rwe.T_out'])
        self.connect('Rwke.q', 'n2.q_out:0') 
        self.connect('Rwka.q', 'n2.q_out:1')
        # node 3 (4 connections)
        self.connect('Rwke.q', 'n3.q_in:0')
        self.connect('n3.T', ['Rinter_e.T_in','Rwke.T_out'])
        self.connect('Rinter_e.q', 'n3.q_out:0')
        # node 4 (4 connections)
        self.connect('Rinter_e.q', 'n4.q_in:0')
        self.connect('n4.T', ['Rv.T_in','Rinter_e.T_out'])
        self.connect('Rv.q', 'n4.q_out:0')
        # node 5 (4 connections)
        self.connect('Rv.q', 'n5.q_in:0')
        self.connect('n5.T', ['Rinter_c.T_in','Rv.T_out'])
        self.connect('Rinter_c.q', 'n5.q_out:0')
        # node 6 (4 connections)
        self.connect('Rinter_c.q', 'n6.q_in:0')
        self.connect('n6.T', ['Rwkc.T_in','Rinter_c.T_out'])
        self.connect('Rwkc.q', 'n6.q_out:0')
        # node 7 (6 connections)
        self.connect('Rwka.q', 'n7.q_in:0')
        self.connect('Rwkc.q', 'n7.q_in:1')
        self.connect('n7.T', ['Rwc.T_in','Rwkc.T_out','Rwka.T_out'])
        self.connect('Rwc.q', 'n7.q_out:0')
        # node 8 (q_out promoted, 'Rwc.T_out', 3 additional connections)
        self.connect('Rwc.q','n8.q_in:0')
        self.connect('Rwa.q','n8.q_in:1')
        self.connect('n8.T',['Rwa.T_out'])


        self.nonlinear_solver = om.NewtonSolver(solve_subsystems=True)
        self.nonlinear_solver.options['iprint'] = 2
        self.nonlinear_solver.options['maxiter'] = 20
        self.linear_solver = om.DirectSolver()
        self.nonlinear_solver.linesearch = om.ArmijoGoldsteinLS()
        self.nonlinear_solver.linesearch.options['maxiter'] = 10
        self.nonlinear_solver.linesearch.options['iprint'] = 2

if __name__ == "__main__":

    p = om.Problem()
    model = p.model

    model.add_subsystem('T_hot', om.IndepVarComp('T', 500., units='K'))
    model.add_subsystem('T_cold', om.IndepVarComp('T', 60, units='K'))
    model.add_subsystem('q_hot', om.IndepVarComp('q', 70., units='W'))
    model.add_subsystem('q_cold', om.IndepVarComp('q', 50, units='W'))
    model.add_subsystem('circuit', Circuit())

    model.connect('T_hot.T', 'circuit.T_hot')
    model.connect('T_cold.T', 'circuit.T_cold')
    model.connect('q_hot.q', 'circuit.q_in')
    model.connect('q_cold.q', 'circuit.q_out')

    p.setup()

    p.check_partials(compact_print=True)
    #om.n2(p)

    # set some initial guesses
    p['circuit.n1.T'] = 500.
    p['circuit.n2.T'] = 350.
    p['circuit.n3.T'] = 300.
    p['circuit.n4.T'] = 250.
    p['circuit.n5.T'] = 200.
    p['circuit.n6.T'] = 150.
    p['circuit.n7.T'] = 100.
    p['circuit.n8.T'] = 60.

    #p.run_model()        